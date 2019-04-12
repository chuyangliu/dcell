#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import time

from pox.core import core
from pox.lib.addresses import EthAddr
import pox.lib.packet as pkt
import pox.openflow.libopenflow_01 as of

import comm

log = core.getLogger()


class Controller(object):

    def __init__(self):
        """Create a Controller instance."""

        # compute number of hosts and switches
        self._num_hosts, self._num_switches = comm.dcell_count()

        # log DCell info
        log.info("init | dcell_k={} | dcell_n={} | num_hosts={} | num_switches={}" \
                 .format(comm.DCELL_K, comm.DCELL_N, self._num_hosts, self._num_switches))

        # add event handlers
        core.listen_to_dependencies(self)

    def _handle_openflow_discovery_LinkEvent(self, event):
        """Triggered when a link is added or removed."""
        link = event.link
        if event.added:  # link added
            log.info("LinkEvent | ({},{}) up".format(link.dpid1, link.dpid2))
        elif event.removed:  # link removed
            log.info("LinkEvent | ({},{}) down".format(link.dpid1, link.dpid2))

    def _handle_openflow_ConnectionUp(self, event):
        """Triggered when a switch is connected to the controller."""
        log.info("ConnectionUp | dpid={}".format(event.dpid))
        Switch(event.connection)  # bind event handlers to switch


class Switch(object):

    def __init__(self, connection):
        self._conn = connection
        self._conn.addListeners(self)
        self._dpid = self._conn.dpid
        self._num_hosts, self._num_switches = comm.dcell_count()

    def _handle_PacketIn(self, event):
        """
        Triggered when the switch's forwarding table does not have a match for the incoming
        packet, causing the packet to be sent from the switch to the controller.
        """
        packet_eth, packet_of = event.parsed, event.ofp
        if not packet_eth.parsed:
            return  # ignore incomplete packet

        mac_src, mac_dst = packet_eth.src.toStr(), packet_eth.dst.toStr()
        log.debug("PacketIn | dpid={} | type={} | ({}) => ({})".format(
            self._dpid, pkt.ethernet.getNameForType(packet_eth.type), mac_src, mac_dst))

        if packet_eth.type == pkt.ethernet.ARP_TYPE:
            # handle ARP requests
            if packet_eth.payload.opcode == pkt.arp.REQUEST:
                self._send_arp_reply(packet_eth, event.port)

        elif packet_eth.type == pkt.ethernet.IP_TYPE:
            # route packet to next hop
            mac_src, mac_dst = comm.mac_to_int(mac_src), comm.mac_to_int(mac_dst)
            self._route_packet(mac_src, mac_dst, packet_of)

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

    def _route_packet(self, mac_src, mac_dst, packet_of):
        """Route packet to next hop and update routing tables.

        Args:
            mac_src (int): MAC address of source host
            mac_dst (int): MAC address of destination host
            packet_of (obj): Packet to be routed
        """
        def _dcell_route(tpl_src, tpl_dst):
            """DCell routing algorithm based on paper."""

            log.debug("dcell_route | mac_src={} | mac_dst={} | tpl_src={} | tpl_dst={}"
                      .format(mac_src, mac_dst, tpl_src, tpl_dst))

            if comm.host_id(tpl_src) == mac_dst:  # next hop is host
                out_port = 1  # port 1 connected to host
                self._push_flow(comm.host_id(tpl_src), mac_src, mac_dst, out_port, packet_of)
                return

            pref = self._common_prefix(tpl_src, tpl_dst)
            pref_len = len(pref)

            if pref_len == comm.DCELL_K:  # same DCell_0
                mini_dpid = self._mini_dpid(comm.host_id(tpl_src))
                self._push_flow(mini_dpid, mac_src, mac_dst, tpl_dst[-1] % comm.DCELL_N + 1)
                time.sleep(comm.SWITCH_MINI_DELAY)  # wait flow entry installed on mini switch
                self._push_flow(comm.host_id(tpl_src), mac_src, mac_dst, 2, packet_of)
                return

            # link between two sub DCells
            mid_src, _ = self._middle_link(pref, tpl_src[pref_len], tpl_dst[pref_len])

            if tpl_src == mid_src:  # route between two DCells
                out_port = comm.DCELL_K - pref_len + 2
                self._push_flow(comm.host_id(tpl_src), mac_src, mac_dst, out_port, packet_of)
                return

            # build route recursively
            _dcell_route(tpl_src, mid_src)

        # route to next hop
        _dcell_route(comm.tuple_id(self._dpid), comm.tuple_id(mac_dst))

    def _push_flow(self, dpid, mac_src, mac_dst, port_dst, data=None):
        """Push new flow entry to a switch.

        Args:
            dpid (int): Data path id of the switch to push the flow entry
            mac_src (int): MAC address of source host
            mac_dst (int): MAC address of destination host
            port_dst (int): Output port of the flow entry
            data (obj): Data to be attached to the flow message
        """
        # create flow message
        msg = of.ofp_flow_mod()
        if data is not None:
            msg.data = data
        msg.match = of.ofp_match(dl_src=self._ethaddr(mac_src), dl_dst=self._ethaddr(mac_dst))
        msg.actions.append(of.ofp_action_output(port=port_dst))

        # send flow message to switch
        core.openflow.connections[dpid].send(msg)
        log.debug("push_flow | dpid={} | mac_src={} | mac_dst={} | port_dst={} | data={}"
                  .format(dpid, mac_src, mac_dst, port_dst, data is not None))

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


def launch(*args, **kw):
    if not core.hasComponent(Controller.__name__):
        core.registerNew(Controller, *args, **kw)
