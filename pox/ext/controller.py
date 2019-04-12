#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from multiprocessing import Lock

from pox.core import core
from pox.lib.addresses import EthAddr
import pox.lib.packet as pkt
import pox.openflow.libopenflow_01 as of

import comm

log = core.getLogger()


class Controller(object):

    def __init__(self):
        """Create a Controller instance."""
        self._mutex = Lock()

        # compute number of hosts and switches
        self._num_hosts, self._num_switches = comm.dcell_count()
        self._num_connected_switches = 0

        # log DCell info
        log.info("init | dcell_k={} | dcell_n={} | num_hosts={} | num_switches={}" \
                 .format(comm.DCELL_K, comm.DCELL_N, self._num_hosts, self._num_switches))

        # add event handlers
        core.listen_to_dependencies(self)

    def _handle_openflow_discovery_LinkEvent(self, event):
        """Triggered when a link is added or removed."""
        link = event.link
        if event.added:  # link added
            log.info("LinkEvent | (%d,%d) up", link.dpid1, link.dpid2)
        elif event.removed:  # link removed
            log.info("LinkEvent | (%d,%d) down", link.dpid1, link.dpid2)

    def _handle_openflow_ConnectionUp(self, event):
        """Triggered when a switch is connected to the controller."""
        log.info("ConnectionUp | dpid=%d", event.dpid)
        # add event handlers to the switch
        Switch(event.connection)
        with self._mutex:
            self._num_connected_switches += 1
            # initial routing table when all switches are connected to the controller
            if self._num_connected_switches == self._num_switches:
                log.info("ConnectionUp | dpid=%d | building routing tables...", event.dpid)
                self._build_all_routes()

    def _build_all_routes(self):
        """Build routing table for each pair of the hosts."""
        for i in range(self._num_hosts):
            for j in range(i + 1, self._num_hosts):
                self._build_route(i + 1, j + 1)

    def _build_route(self, mac_src, mac_dst):
        """Build routing path between two hosts.

        Args:
            mac_src (int): MAC address of source host
            mac_dst (int): MAC address of destination host
        """

        def _build_dcell_route(tpl_src, tpl_dst):
            """DCellRouting(src, dst) from the paper."""

            pref = self._common_prefix(tpl_src, tpl_dst)
            pref_len = len(pref)

            if pref == comm.DCELL_K:  # same DCell_0
                switch0_dpid = self._dcell0_switch_dpid(mac_src)
                self._push_flow(mac_src, mac_src, mac_dst, 2)  # port 2 connected to DCell_0 switch
                self._push_flow(mac_dst, mac_dst, mac_src, 2)  # port 2 connected to DCell_0 switch
                self._push_flow(switch0_dpid, mac_src, mac_dst, tpl_dst % comm.DCELL_N + 2)
                self._push_flow(switch0_dpid, mac_dst, mac_src, tpl_src % comm.DCELL_N + 2)
                return

            # link between two sub DCells
            mid_src, mid_dst = self._middle_link(pref, tpl_src[pref_len], tpl_dst[pref_len])
            self._push_flow(comm.host_id(mid_src), mac_src, mac_dst, comm.DCELL_K - pref_len + 2)
            self._push_flow(comm.host_id(mid_dst), mac_dst, mac_src, comm.DCELL_K - pref_len + 2)

            # build routes recursively
            _build_dcell_route(tpl_src, mid_src)
            _build_dcell_route(mid_dst, tpl_dst)

        tpl_src = comm.tuple_id(mac_src)
        tpl_dst = comm.tuple_id(mac_dst)
        log.info("build_route | mac_src=%d | mac_dst=%d | tpl_src=%s | tpl_dst=%s",
                 comm.host_id(tpl_src), comm.host_id(tpl_dst), tpl_src, tpl_dst)

        _build_dcell_route(tpl_src, tpl_dst)

    def _push_flow(self, dpid, mac_src, mac_dst, port_dst):
        """Push new flow entry to a switch.

        Args:
            dpid (int): data path id of the switch to push the flow entry
            mac_src (int): MAC address of source host
            mac_dst (int): MAC address of destination host
            port_dst (int): output port of the flow entry
        """
        # create flow message
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match(dl_src=self._ethaddr(mac_src), dl_dst=self._ethaddr(mac_dst))
        msg.actions.append(of.ofp_action_output(port=port_dst))

        # send flow message to switch
        conn = core.openflow.connections[dpid]
        conn.send(msg)

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

    def _ethaddr(self, mac):
        """Convert a mac address integer to a EthAddr object."""
        return EthAddr(comm.mac_to_str(mac))

    def _dcell0_switch_dpid(self, host_id):
        """Return the dpid of the mini switch in the DCell_0 where a given host is located."""
        return self._num_hosts + 1 + (host_id - 1) / comm.DCELL_N


class Switch(object):

    def __init__(self, connection):
        self._conn = connection
        self._conn.addListeners(self)
        self._dpid = self._conn.dpid
        self._mac_port = {}  # mac_addr -> switch_port mapping

    def _handle_PacketIn(self, event):
        """
        Triggered when the switch's forwarding table does not have a match for the incoming
        packet, causing the packet to be sent from the switch to the controller.
        """
        packet_eth = event.parsed
        if not packet_eth.parsed:
            log.warning("Ignore incomplete packet")
            return

        # reply ARP request
        if packet_eth.type == packet_eth.ARP_TYPE and packet_eth.payload.opcode == pkt.arp.REQUEST:

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
            msg.in_port = event.port
            self._conn.send(msg)

            log.info("PacketIn | dpid=%d | (%s,%s) => (%s,%s)",
                     self._dpid, ip_src.toStr(), mac_src.toStr(), ip_dst.toStr(), mac_dst.toStr())


def launch(*args, **kw):
    if not core.hasComponent(Controller.__name__):
        core.registerNew(Controller, *args, **kw)
