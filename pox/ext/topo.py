#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.topo import Topo

from comm import *


class DCellTopo(Topo):

    def build(self, tree):
        """Build a DCell network topology, called by Topo.__init__().

        Args:
            tree (bool): whether to build a tree topology (for testing)
        """
        if tree:
            self._build_tree()
        else:
            self._build_dcell()

    def _build_tree(self):
        # 2-layer tree
        h1 = self._add_host("h1")
        h2 = self._add_host("h2")
        h3 = self._add_host("h3")
        h4 = self._add_host("h4")
        s1 = self._add_switch("s1")
        s2 = self._add_switch("s2")
        s3 = self._add_switch("s3")
        self._add_link(s1, h1)
        self._add_link(s1, h2)
        self._add_link(s2, h3)
        self._add_link(s3, h4)
        self._add_link(s3, s1)
        self._add_link(s3, s2)

    def _build_dcell(self):
        self._hosts = {}     # (k+1)-tuple -> host name
        self._switches = {}  # (k+1)-tuple -> switch name
        self._nhost = 1
        self._nswitch = 1
        self._nswitch0, nswitch = dcell_count(DCELL_LEVEL, DCELL_N)

        def build_helper(self, pref, n, level):
            if level == 0: # build DCell_0
                self._nswitch0 += 1
                switch_name0 = "s" + str(self._nswitch0)
                s0 = self._add_switch(switch_name0)
                for i in range(n):
                    id = pref + "." + str(i)
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
                build_helper(self, pref + "." + str(i), n, level - 1)

            for i in range(t[level - 1]):  # connect the DCell_(l-1)s
                for j in range(i + 1, g[level]):
                    n1 = pref + "." + str(i) + "." + str(j - 1)
                    n2 = pref + "." + str(j) + "." + str(i)
                    s1 = self._switches[n1]
                    s2 = self._switches[n2]
                    self._add_link(s1, s2)
                    print "(" + n1 + "," + s1 + ")...(" + n2 + "," + s2 + ")"

        t = []  # the number of servers in DCell_l
        g = []  # the number of DCell_(l-1)s in DCell_l
        t.append(DCELL_N)
        g.append(1)
        for i in range(DCELL_LEVEL):
            g.append(t[i] + 1)
            t.append(g[i + 1] * t[i])
        self._nswitch0 = t[DCELL_LEVEL]
        pref = "DCell" + str(DCELL_LEVEL)
        build_helper(self, pref, DCELL_N, DCELL_LEVEL)  # construct DCell

    def _add_host(self, name):
        host_id = int(name[1:])
        return self.addHost(name, mac=mac_to_str(host_id))  # set mac equals to host id

    def _add_switch(self, name):
        return self.addSwitch(name, cls=SWITCH_CLS)

    def _add_link(self, node1, node2):
        return self.addLink(node1, node2, bw=LINK_BW)
