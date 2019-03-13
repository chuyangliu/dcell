#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()


class Handler(object):
    """A Handler object is created for each switch that connects."""

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

            log.info("(%s,%d) => (%s,%d) installed", mac_in, port_in, mac_out, port_out)
        else:
            # flood the packet out everything but the input port
            self._send_packet(packet_in, of.OFPP_ALL)

    def _send_packet(self, data, port_out):
        packet_out = of.ofp_packet_out()
        packet_out.data = data
        packet_out.actions.append(of.ofp_action_output(port=port_out))
        self._connection.send(packet_out)


def launch():
    """Starts the component."""
    core.openflow.addListenerByName("ConnectionUp", lambda event: Handler(event.connection))
