#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from pox.core import core
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of

log = core.getLogger()


class TopoStat(object):
    _core_name = "topo_stat"  # usage: core.topo_stat.*

    def __init__(self):
        core.listen_to_dependencies(self)
        self.link_num = {}

    def _handle_openflow_discovery_LinkEvent(self, event):
        link = event.link.uni
        s1 = dpid_to_str(link.dpid1, alwaysLong=True)
        s2 = dpid_to_str(link.dpid2, alwaysLong=True)
        key = (s1, s2)
        if event.added:  # link added
            log.info("(%s,%s) link up", s1, s2)
            if key in self.link_num:
                self.link_num[key] += 1
            else:
                self.link_num[key] = 1
        elif event.removed:  # link removed
            log.info("(%s,%s) link down", s1, s2)
            self.link_num.pop(key, None)


class Handler(object):

    def __init__(self, connection):
        self._connection = connection
        self._connection.addListeners(self)
        self._mac_port = {}

    def _handle_PacketIn(self, event):
        packet, packet_in, port_in = event.parsed, event.ofp, event.port

        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        mac_in, mac_out = str(packet.src), str(packet.dst)
        self._mac_port[mac_in] = port_in

        if mac_out in self._mac_port:
            port_out = self._mac_port[mac_out]

            # match rules
            match = of.ofp_match()
            match.dl_src = packet.src
            match.dl_dst = packet.dst
            match.in_port = port_in

            # push down flow entry
            flow_mod = of.ofp_flow_mod()
            flow_mod.match = match
            flow_mod.actions.append(of.ofp_action_output(port=port_out))
            self._connection.send(flow_mod)

            # push down origin packet
            self._send_packet(packet_in, port_out)

            log.info("(%s,%d)=>(%s,%d) installed", mac_in, port_in, mac_out, port_out)
        else:
            # flood the packet out everything but the input port
            self._send_packet(packet_in, of.OFPP_ALL)

    def _send_packet(self, packet_in, port_out):
        packet_out = of.ofp_packet_out()
        packet_out.data = packet_in
        packet_out.actions.append(of.ofp_action_output(port=port_out))
        self._connection.send(packet_out)


def launch():
    if not core.hasComponent(TopoStat._core_name):
        core.registerNew(TopoStat)
    core.openflow.addListenerByName("ConnectionUp", lambda event: Handler(event.connection))
