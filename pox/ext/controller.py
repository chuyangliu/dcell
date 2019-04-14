#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import numbers
from multiprocessing import Lock

from pox.core import core
from pox.lib.addresses import EthAddr
import pox.lib.packet as pkt
import pox.openflow.libopenflow_01 as of

import comm

log = core.getLogger()


class FlowTable(object):
    """In-memory dictionary recording flow entries in each switch.

    Each flow entry consists of a Match object and an Action object. A Match object matches
    source and destination MAC addresses of an incoming Ethernet frame. An Action object specifies
    the output port on the switch to forward the frame.
    """

    def __init__(self):
        # map: dpid => [out_port => [set of (mac_src,mac_dst) tuples]]
        # flow entry in each switch can be represented as (mac_src, mac_dst, out_port)
        self._table = {}

    def add_flow(self, dpid, mac_src, mac_dst, out_port):
        """Add one flow entry if not exist."""
        if dpid not in self._table:
            self._table[dpid] = {}
        if out_port not in self._table[dpid]:
            self._table[dpid][out_port] = set()
        self._table[dpid][out_port].add((mac_src, mac_dst))

    def del_flow(self, dpid, mac_src=None, mac_dst=None, out_port=None):
        """Remove matched flow entries if exist."""
        if dpid not in self._table:
            return

        match_addr = mac_src is not None and mac_dst is not None
        match_port = out_port is not None

        if match_port:
            if match_addr:
                self._table[dpid][out_port].discard((mac_src, mac_dst))  # delete one flow
            else:
                self._table[dpid].pop(out_port, None)  # delete all flows with out_port
        else:
            if match_addr:
                for _, tuples in self._table[dpid].iteritems():
                    tuples.discard((mac_src, mac_dst))  # delete all flows with (mac_src, mac_dst)
            else:
                self._table[dpid] = {}  # delete all flows

    def flow_addrs(self, dpid, out_port=None):
        """Get matched flow entries."""
        addrs = set()
        if dpid in self._table:
            if out_port is None:
                for _, tuples in self._table[dpid].iteritems():
                    addrs = addrs.union(tuples)
            elif out_port in self._table[dpid]:
                addrs = self._table[dpid][out_port]
        return addrs


class Controller(object):

    def __init__(self):
        """Create a Controller instance."""

        # get number of hosts and switches
        self._num_hosts, self._num_switches = comm.count_nodes()

        # counter for connected switches
        self._num_connect = 0

        # broken links
        self._bad_links = set()

        # keep track of flow entries in each switch
        self._flow_table = FlowTable()

        # mutex locks
        self._mutex_connect = Lock()
        self._mutex_link_state = Lock()

        # add event handlers
        core.listen_to_dependencies(self)

        # log DCell info
        log.info("init | dcell_k={} | dcell_n={} | num_hosts={} | num_switches={}" \
                 .format(comm.DCELL_K, comm.DCELL_N, self._num_hosts, self._num_switches))

    def _handle_openflow_discovery_LinkEvent(self, event):
        """Triggered when a link is added or removed."""

        # get link with normalized dpid order
        link = event.link.uni
        link_tuple = (link.dpid1, link.dpid2)

        with self._mutex_link_state:
            rebuild = set()

            if event.added and link_tuple in self._bad_links:  # link recovered
                self._bad_links.discard(link_tuple)
                log.info("LinkEvent | ({}:{},{}:{}) up"
                         .format(link.dpid1, link.port1, link.dpid2, link.port2))

                # rebuild all routes that pass the two switches
                # edge case: middle link broken and recovered, when mac_src == mid_src
                rebuild = rebuild.union(self._flow_table.flow_addrs(link.dpid1))
                rebuild = rebuild.union(self._flow_table.flow_addrs(link.dpid2))

            elif event.removed and link_tuple not in self._bad_links:  # link broken
                self._bad_links.add(link_tuple)
                log.info("LinkEvent | ({}:{},{}:{}) down"
                         .format(link.dpid1, link.port1, link.dpid2, link.port2))

                # rebuild all routes that pass the broken link
                rebuild = rebuild.union(self._flow_table.flow_addrs(link.dpid1, link.port1))
                rebuild = rebuild.union(self._flow_table.flow_addrs(link.dpid2, link.port2))

            # rebuild routes
            for mac_src, mac_dst in rebuild:
                log.debug("LinkEvent | rebuild routes | ({}) => ({})"
                          .format(comm.tuple_id(mac_src), comm.tuple_id(mac_dst)))
                self._build_route(mac_src, mac_dst)

    def _handle_openflow_ConnectionUp(self, event):
        """Triggered when a switch is connected to the controller."""

        # add event handlers to the switch
        Switch(event.connection)
        log.info("ConnectionUp | dpid={}".format(event.dpid))

        # check connected switches
        with self._mutex_connect:
            self._num_connect += 1
            if self._num_connect == self._num_switches:
                self._build_all_routes()  # build routing tables after all switches connected

    def _build_all_routes(self):
        """Build routing table for each pair of the hosts."""
        for i in range(self._num_hosts):
            for j in range(i + 1, self._num_hosts):
                # build bidirectional routes
                self._build_route(i + 1, j + 1)
                self._build_route(j + 1, i + 1)

    def _build_route(self, mac_src, mac_dst):
        """Build routing path from source host to destination host.

        Args:
            mac_src (int): MAC address of source host
            mac_dst (int): MAC address of destination host
        """
        def _build_dcell_route(tpl_src, tpl_dst):
            """DCellRouting(src, dst) from the paper."""

            log.debug("build_dcell_route | mac_src={} | mac_dst={} | tpl_src={} | tpl_dst={}"
                      .format(mac_src, mac_dst, tpl_src, tpl_dst))

            if tpl_src == tpl_dst:
                return  # skip routing to self

            pref = self._common_prefix(tpl_src, tpl_dst)
            pref_len = len(pref)

            if pref_len == comm.DCELL_K:  # same DCell_0

                # check mini switch connection
                mini_dpid = self._mini_dpid(comm.host_id(tpl_src))
                bad_mini_in = self._is_bad_link(mini_dpid, tpl_src)
                bad_mini_out = self._is_bad_link(mini_dpid, tpl_dst)
                if bad_mini_in or bad_mini_out:
                    # rack failure handle not implemented
                    log.error("build_dcell_route | cannot handle rack failure | mini_switch={}"
                              .format(mini_dpid))
                    return

                # add flow entries to mini switch
                self._add_flow(mini_dpid, mac_src, mac_dst, tpl_dst[-1] % comm.DCELL_N + 1)
                # add flow entries to host switch (port 2 connected to mini switch)
                self._add_flow(comm.host_id(tpl_src), mac_src, mac_dst, 2)

                return

            # get the link connecting two sub DCells
            mid_src, mid_dst = self._middle_link(pref, tpl_src[pref_len], tpl_dst[pref_len])

            # route to proxy if middle link is broken
            if self._is_bad_link(mid_src, mid_dst):
                proxy = self._select_proxy(tpl_src, tpl_dst, pref)
                if proxy is None:
                    log.warn("build_dcell_route | no proxy node | src={} | dst={}"
                             .format(tpl_src, tpl_dst))
                else:
                    _build_dcell_route(tpl_src, proxy)
                    _build_dcell_route(proxy, tpl_dst)
                return

            # update routing tables on the middle link switches
            out_port = comm.DCELL_K - pref_len + 2
            self._add_flow(comm.host_id(mid_src), mac_src, mac_dst, out_port)

            # build routes recursively
            _build_dcell_route(tpl_src, mid_src)
            _build_dcell_route(mid_dst, tpl_dst)

        # build routes among switches
        _build_dcell_route(comm.tuple_id(mac_src), comm.tuple_id(mac_dst))

        # build routes from destination switch to host (port 1 connected to host)
        self._add_flow(mac_dst, mac_src, mac_dst, 1)

    def _add_flow(self, dpid, mac_src, mac_dst, out_port):
        """Add new flow entry to a switch. Replace existing flow entry."""

        # delete existing flows
        self._del_flow(dpid, mac_src, mac_dst)

        # create flow add message
        msg = of.ofp_flow_mod(command=of.OFPFC_ADD)
        msg.match = of.ofp_match(dl_src=self._ethaddr(mac_src), dl_dst=self._ethaddr(mac_dst))
        msg.actions.append(of.ofp_action_output(port=out_port))

        # send flow message to switch
        core.openflow.connections[dpid].send(msg)

        # update flow table
        self._flow_table.add_flow(dpid, mac_src, mac_dst, out_port)

    def _del_flow(self, dpid, mac_src=None, mac_dst=None, out_port=of.OFPP_NONE):
        """Remove flow entries from a switch."""
        if mac_src is not None:
            eth_src = self._ethaddr(mac_src)
        if mac_dst is not None:
            eth_dst = self._ethaddr(mac_dst)

        # create flow remove message
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE, out_port=out_port)
        msg.match = of.ofp_match(dl_src=eth_src, dl_dst=eth_dst)

        # send flow message to switch
        core.openflow.connections[dpid].send(msg)

        # update local flow table
        out_port = None if out_port == of.OFPP_NONE else out_port
        self._flow_table.del_flow(dpid, mac_src, mac_dst, out_port)

    def _select_proxy(self, tpl_src, tpl_dst, pref):
        """Select a proxy node if the middle link between two nodes fail."""
        pref_len = len(pref)
        num_dcells = comm.count_dcells(comm.DCELL_K - pref_len)  # number of DCell_(k-1)

        # check neighbor DCells one by one
        for i in range(1, num_dcells):

            idx = (tpl_src[pref_len] + i) % num_dcells
            if idx == tpl_dst[pref_len]:
                continue  # cannot directly route to destination due to broken link

            mid_src, mid_dst = self._middle_link(pref, tpl_src[pref_len], idx)
            if self._is_bad_link(mid_src, mid_dst):
                continue  # broken middle link

            return mid_dst  # selected proxy node

        return None  # no proxy node

    def _is_bad_link(self, s1, s2):
        """Check whether the link between two switches is broken."""
        host1 = s1 if isinstance(s1, numbers.Integral) else comm.host_id(s1)
        host2 = s2 if isinstance(s2, numbers.Integral) else comm.host_id(s2)
        if host1 > host2:
            host1, host2 = host2, host1
        return (host1, host2) in self._bad_links

    def _middle_link(self, pref, src_idx, dst_idx):
        """Get the middle links that connects two sub DCells."""
        pref_len = len(pref)

        swap = False
        if src_idx > dst_idx:
            src_idx, dst_idx = dst_idx, src_idx
            swap = True

        src_mid_suffix = comm.tuple_id(dst_idx, comm.DCELL_K - pref_len - 1)
        dst_mid_suffix = comm.tuple_id(src_idx + 1, comm.DCELL_K - pref_len - 1)
        src_mid = pref + [src_idx] + src_mid_suffix
        dst_mid = pref + [dst_idx] + dst_mid_suffix

        if swap:
            src_mid, dst_mid = dst_mid, src_mid

        return src_mid, dst_mid

    def _common_prefix(self, list1, list2):
        """Return the common prefix entries (as a new list) of two given lists."""
        ans = []
        for i in range(min(len(list1), len(list2))):
            if list1[i] == list2[i]:
                ans.append(list1[i])
            else:
                break
        return ans

    def _mini_dpid(self, host_id):
        """Return the dpid of the mini switch in the DCell_0 where a given host is located."""
        return self._num_hosts + 1 + (host_id - 1) / comm.DCELL_N

    def _ethaddr(self, mac):
        """Convert a mac address integer to a EthAddr object."""
        return EthAddr(comm.mac_to_str(mac))


class Switch(object):

    def __init__(self, connection):
        self._conn = connection
        self._conn.addListeners(self)
        self._dpid = self._conn.dpid

    def _handle_PacketIn(self, event):
        """
        Triggered when the switch's forwarding table does not have a match for the incoming
        packet, causing the packet to be sent from the switch to the controller.
        """
        packet_eth = event.parsed
        if not packet_eth.parsed:
            return  # ignore incomplete packet

        mac_src, mac_dst = packet_eth.src.toStr(), packet_eth.dst.toStr()
        log.debug("PacketIn | dpid={} | type={} | ({}) => ({})".format(
            self._dpid, pkt.ethernet.getNameForType(packet_eth.type), mac_src, mac_dst))

        # reply ARP request
        if packet_eth.type == packet_eth.ARP_TYPE and packet_eth.payload.opcode == pkt.arp.REQUEST:
            self._send_arp_reply(packet_eth, event.port)

    def _send_arp_reply(self, packet_eth, in_port):
        # parse ARP request, get destination mac address
        arp_req = packet_eth.payload
        ip_src, ip_dst = arp_req.protosrc, arp_req.protodst
        mac_src, mac_dst = packet_eth.src, EthAddr(comm.ip_to_mac(ip_dst.toStr()))

        # create an ARP response packet
        arp_resp = pkt.arp()
        arp_resp.opcode = pkt.arp.REPLY
        arp_resp.protosrc = ip_dst
        arp_resp.protodst = ip_src
        arp_resp.hwsrc = mac_dst
        arp_resp.hwdst = mac_src

        # pack inside a ethernet frame
        reply = pkt.ethernet(src=mac_dst, dst=mac_src)
        reply.type = pkt.ethernet.ARP_TYPE
        reply.set_payload(arp_resp)

        # send response
        msg = of.ofp_packet_out()
        msg.data = reply.pack()
        msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
        msg.in_port = in_port
        self._conn.send(msg)

        log.debug("send_arp_reply | dpid={} | ({},{}) => ({},{})".format(
            self._dpid, ip_src.toStr(), mac_src.toStr(), ip_dst.toStr(), mac_dst.toStr()))


def launch(*args, **kw):
    if not core.hasComponent(Controller.__name__):
        core.registerNew(Controller, *args, **kw)
