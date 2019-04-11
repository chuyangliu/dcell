#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from multiprocessing import Lock

from pox.core import core
from pox.lib.addresses import EthAddr
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
                 .format(comm.DCELL_LEVEL, comm.DCELL_N, self._num_hosts, self._num_switches))

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
        tpl_src = comm.dcell_tuple_id(mac_src)
        tpl_dst = comm.dcell_tuple_id(mac_dst)
        log.info("build_route | mac_src=%d | mac_dst=%d | tpl_src=%s | tpl_dst=%s",
                 comm.dcell_host_id(tpl_src), comm.dcell_host_id(tpl_dst), tpl_src, tpl_dst)
        # TODO


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
            log.info("PacketIn | dpid=%d | (%s,%d) => (%s,) broadcasted",
                     self._dpid, mac_src, port_src, mac_dst)
        else:
            # destination port known, add new flow entry
            port_dst = self._mac_port[mac_dst]
            msg = of.ofp_flow_mod()
            msg.data = packet_of
            msg.match = of.ofp_match(dl_src=packet_eth.src, dl_dst=packet_eth.dst)
            msg.actions.append(of.ofp_action_output(port=port_dst))
            self._conn.send(msg)
            log.info("PacketIn | dpid=%d | (%s,%d) => (%s,%d) flow added",
                     self._dpid, mac_src, port_src, mac_dst, port_dst)


def launch(*args, **kw):
    if not core.hasComponent(Controller.__name__):
        core.registerNew(Controller, *args, **kw)
