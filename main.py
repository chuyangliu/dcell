#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

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

    def build(self, level, n, link_bw=100, switch_cls=OVSKernelSwitch):
        """Build a DCell network topology.

        Args:
            level (int): DCell level to build
            n (int): Number of hosts in a DCell-0
            link_bw (int): Data link bandwidth (Mbps)
            switch_cls (obj): Switch class
        """
        self._hosts = {}     # (k+1)-tuple -> host name
        self._switches = {}  # (k+1)-tuple -> switch name
        self._nhost = 1
        self._nswitch = 1
        self._nswitch0 = 0

        def build_helper(self, pref, n, level, link_bw, switch_cls):
            if level == 0: # build DCell_0
                self._nswitch0 += 1
                switch_name0 = "s" + str(self._nswitch0)
                s0 = self.addSwitch(switch_name0, cls=switch_cls)
                for i in range(n):
                    id = pref + str(i)
                    # add a host
                    host_name = "h" + str(self._nhost)
                    self._nhost += 1
                    host = self.addHost(host_name)
                    self._hosts[id] = host

                    # add a switch combined with the host
                    switch_name = "s" + str(self._nswitch)
                    self._nswitch += 1
                    switch = self.addSwitch(switch_name, cls=switch_cls)
                    self._switches[id] = switch

                    self.addLink(switch, host, bw=link_bw)
                    self.addLink(s0, switch)
                    print(id + " | (" + host_name + "..." + switch_name + ") "
                          + "(" + switch_name0 + "..." + switch_name + ")")
                return

            for i in range(g[level]):  # build DCell_(l-1)s
                build_helper(self, pref + str(i), n, level - 1, link_bw, switch_cls)

            for i in range(t[level - 1]):  # connect the DCell_(l-1)s
                for j in range(i + 1, g[level]):
                    n1 = pref + str(i) + str(j - 1)
                    n2 = pref + str(j) + str(i)
                    s1 = self._switches[n1]
                    s2 = self._switches[n2]
                    self.addLink(s1, s2)
                    print("(" + n1 + "," + s1 + ")...(" + n2 + "," + s2 + ")")

        t = []  # the number of servers in DCell_l
        g = []  # the number of DCell_(l-1)s in DCell_l
        t.append(n)
        g.append(1)
        for i in range(level):
            g.append(t[i] + 1)
            t.append(g[i + 1] * t[i])
        self._nswitch0 = t[level]
        pref = "DCell" + str(level) + "-" + str(n) + "."
        build_helper(self, pref, n, level, link_bw, switch_cls)  # construct DCell

        # # multi-path test
        # s1 = self.addSwitch("s1", cls=switch_cls)
        # s2 = self.addSwitch("s2", cls=switch_cls)
        # s3 = self.addSwitch("s3", cls=switch_cls)
        # s4 = self.addSwitch("s4", cls=switch_cls)
        # h1 = self.addHost("h1")
        # h2 = self.addHost("h2")
        # self.addLink(s1, h1)
        # self.addLink(s3, h2)
        # self.addLink(s1, s2)
        # self.addLink(s1, s4)
        # self.addLink(s3, s2)
        # self.addLink(s3, s4)
        
        # # 1-layer tree
        # print("in build")
        # h1 = self.addHost("h1")
        # h2 = self.addHost("h2")
        # h3 = self.addHost("h3")
        # s1 = self.addSwitch("s1", cls=switch_cls)
        # self.addLink(s1, h1, bw=link_bw)
        # self.addLink(s1, h2, bw=link_bw)
        # self.addLink(s1, h3, bw=link_bw)

        # 2-layer tree
        # h1 = self.addHost("h1")
        # h2 = self.addHost("h2")
        # h3 = self.addHost("h3")
        # h4 = self.addHost("h4")
        # s1 = self.addSwitch("s1", cls=switch_cls)
        # s2 = self.addSwitch("s2", cls=switch_cls)
        # s3 = self.addSwitch("s3", cls=switch_cls)
        # self.addLink(s1, h1, bw=link_bw)
        # self.addLink(s1, h2, bw=link_bw)
        # self.addLink(s2, h3, bw=link_bw)
        # self.addLink(s3, h4, bw=link_bw)
        # self.addLink(s3, s1, bw=link_bw)
        # self.addLink(s3, s2, bw=link_bw)


def main():
    net = Mininet(
        topo=DCellTopo(level=1, n=4),
        link=TCLink,
        controller=DCellController,
        autoSetMacs=True
    )
    net.start()
    time.sleep(3)
    net.pingAll()
    # net.iperf((net["h1"], net["h3"]))
    # CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
