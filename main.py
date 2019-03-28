#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import sys
import time

from mininet.topo import Topo
from mininet.node import Controller, OVSKernelSwitch
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


class DCellController(Controller):
    """
    Run a POX controller for DCell routing in a separate process.
    Log location: /tmp/c0.log
    """
    def __init__(self, name):
        args = {
            "name": name,
            "command": "./pox/pox.py",
            "cargs": (
                # "--verbose "
                "openflow.of_01 --port=%d "
                "openflow.discovery --link_timeout=1 "  # 1 sec
                "dcell_pox "
            )
        }
        Controller.__init__(self, **args)


class DCellTopo(Topo):

    def _add_host(self, name):
        return self.addHost(name)

    def _add_switch(self, name):
        return self.addSwitch(name, cls=OVSKernelSwitch)

    def _add_link(self, node1, node2):
        return self.addLink(node1, node2, bw=self._link_bw)

    def build(self, level, n, link_bw):
        """Build a DCell network topology, called by Topo.__init__()

        Args:
            level (int): DCell level to build
            n (int): Number of hosts in a DCell-0
            link_bw (int): Data link bandwidth (Mbps)
        """
        self._link_bw = link_bw

        self._hosts = {}     # (k+1)-tuple -> host name
        self._switches = {}  # (k+1)-tuple -> switch name
        self._nhost = 1
        self._nswitch = 1
        self._nswitch0 = 0

        def build_helper(self, pref, n, level):
            if level == 0: # build DCell_0
                self._nswitch0 += 1
                switch_name0 = "s" + str(self._nswitch0)
                s0 = self._add_switch(switch_name0)
                for i in range(n):
                    id = pref + str(i)
                    # add a host
                    host_name = "h" + str(self._nhost)
                    self._nhost += 1
                    host = self._add_host(host_name)
                    self._hosts[id] = host

                    # add a switch combined with the host
                    switch_name = "s" + str(self._nswitch)
                    self._nswitch += 1
                    switch = self._add_switch(switch_name)
                    self._switches[id] = switch

                    self._add_link(switch, host)
                    self._add_link(s0, switch)
                    print(id + " | (" + host_name + "..." + switch_name + ") "
                          + "(" + switch_name0 + "..." + switch_name + ")")
                return

            for i in range(g[level]):  # build DCell_(l-1)s
                build_helper(self, pref + str(i), n, level - 1)

            for i in range(t[level - 1]):  # connect the DCell_(l-1)s
                for j in range(i + 1, g[level]):
                    n1 = pref + str(i) + str(j - 1)
                    n2 = pref + str(j) + str(i)
                    s1 = self._switches[n1]
                    s2 = self._switches[n2]
                    self._add_link(s1, s2)
                    print "(" + n1 + "," + s1 + ")...(" + n2 + "," + s2 + ")"

        t = []  # the number of servers in DCell_l
        g = []  # the number of DCell_(l-1)s in DCell_l
        t.append(n)
        g.append(1)
        for i in range(level):
            g.append(t[i] + 1)
            t.append(g[i + 1] * t[i])
        self._nswitch0 = t[level]
        pref = "DCell" + str(level) + "-" + str(n) + "."
        build_helper(self, pref, n, level)  # construct DCell

        # 1-layer tree
        # h1 = self._add_host("h1")
        # h2 = self._add_host("h2")
        # h3 = self._add_host("h3")
        # s1 = self._add_switch("s1")
        # self._add_link(s1, h1)
        # self._add_link(s1, h2)
        # self._add_link(s1, h3)

        # 2-layer tree
        # h1 = self._add_host("h1")
        # h2 = self._add_host("h2")
        # h3 = self._add_host("h3")
        # h4 = self._add_host("h4")
        # s1 = self._add_switch("s1")
        # s2 = self._add_switch("s2")
        # s3 = self._add_switch("s3")
        # self._add_link(s1, h1)
        # self._add_link(s1, h2)
        # self._add_link(s2, h3)
        # self._add_link(s3, h4)
        # self._add_link(s3, s1)
        # self._add_link(s3, s2)


def main():
    # command-line args
    cli = len(sys.argv) >= 2 and sys.argv[1] == "cli"

    # start a net
    net = Mininet(
        topo=DCellTopo(level=1, n=3, link_bw=100),
        link=TCLink,
        controller=DCellController,
        autoSetMacs=True
    )
    net.start()
    time.sleep(3)  # wait controller starts

    # run tests
    if cli:
        CLI(net)
    else:
        net.pingAll()
        net.iperf((net["h1"], net["h3"]))

    # stop net
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
