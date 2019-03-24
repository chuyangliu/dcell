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
        self._hosts = {}
        self._switches = {}
        self._nhost = 1
        self._nswitch = 1

        def build_helper(self, pref, n, level, tl, gl, link_bw, switch_cls):
            if level == 0: # build DCell0
                switch_name = "s" + str(self._nswitch)
                print(switch_name)
                self._nswitch += 1
                s = self.addSwitch(switch_name, cls=switch_cls)
                dcell0_hosts = []
                dcell0_switches = []
                for i in range(n):
                    switch_id = pref + "s" + str(i)
                    switch_name = "s" + str(self._nswitch)
                    print(switch_name)
                    self._nswitch += 1
                    self._switches[switch_id] = switch_name
                    dcell0_switches.append(self.addSwitch(switch_name, cls=switch_cls))

                    host_id = pref + "h" + str(i)
                    host_name = "h" + str(self._nhost)
                    print(host_name)
                    self._nhost += 1
                    self._hosts[host_id] = host_name
                    dcell0_hosts.append(self.addHost(host_name))

                    self.addLink(dcell0_switches[i], dcell0_hosts[i], bw=link_bw)
                    self.addLink(s, dcell0_switches[i])
                return

        pref = ""
        tl = n  # the number of servers in DCell_l
        gl = 1  # the number of DCell_(l-1)s in DCell_l
        for i in range(level + 1):
            build_helper(self, pref, n, i, tl, gl, link_bw, switch_cls)
            gl = tl + 1
            tl = gl * tl
        
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
        topo=DCellTopo(level=0, n=4),
        link=TCLink,
        controller=DCellController,
        autoSetMacs=True
    )
    net.start()
    time.sleep(3)
    net.pingAll()
    net.iperf((net["h1"], net["h3"]))
    # CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
