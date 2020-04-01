#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from pox.core import core
import pox.openflow.libopenflow_01 as of

import comm

log = core.getLogger()


class Controller(object):

    def __init__(self):
        """Create a Controller instance."""
        log.info("TreeController init")
        # add event handlers
        core.listen_to_dependencies(self)

    def _handle_openflow_ConnectionUp(self, event):
        """Triggered when a switch is connected to the controller."""
        log.info("ConnectionUp | dpid=%d", event.dpid)
        # add event handlers to the switch
        Switch(event.connection)


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

        packet_of, port_src = event.ofp, event.port
        mac_src, mac_dst = str(packet_eth.src), str(packet_eth.dst)

        # add mac->port mapping
        self._mac_port[mac_src] = port_src

        if mac_dst not in self._mac_port:
            # destination port unknown, broadcast (ARP) request
            msg = of.ofp_packet_out()
            msg.data = packet_of
            msg.actions.append(of.ofp_action_output(port=of.OFPP_ALL))
            self._conn.send(msg)
            log.debug("PacketIn | dpid=%d | (%s,%d) => (%s,) broadcasted",
                      self._dpid, mac_src, port_src, mac_dst)
        else:
            # destination port known, add new flow entry
            port_dst = self._mac_port[mac_dst]
            msg = of.ofp_flow_mod()
            msg.data = packet_of
            msg.match = of.ofp_match(dl_src=packet_eth.src, dl_dst=packet_eth.dst)
            msg.actions.append(of.ofp_action_output(port=port_dst))
            self._conn.send(msg)
            log.debug("PacketIn | dpid=%d | (%s,%d) => (%s,%d) flow added",
                      self._dpid, mac_src, port_src, mac_dst, port_dst)


def launch(*args, **kw):
    if not core.hasComponent(Controller.__name__):
        core.registerNew(Controller, *args, **kw)
