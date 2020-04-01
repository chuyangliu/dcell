#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.topo import Topo

import comm


class DCellTopo(Topo):

    def build(self, tree):
        """Build a DCell network topology, called by Topo.__init__().

        Args:
            tree (bool): true if use tree topology, false otherwise
        """
        if tree:
            self._build_tree()
        else:
            self._build_dcell()

    def _build_tree(self):
        """Build a two-level tree that has 20 servers for testing."""
        print "build_tree"
        switches = []
        switches.append(self._add_switch("s1"))
        switches.append(self._add_switch("s2"))
        switches.append(self._add_switch("s3"))
        switches.append(self._add_switch("s4"))
        switches.append(self._add_switch("s5"))
        switches.append(self._add_switch("s6"))
        for i in range(5):
            self._add_link(switches[5], switches[i])
        for i in range(20):
            host_name = "h" + str(i + 1)
            host = self._add_host(host_name)
            self._add_link(host, switches[i / 4])

    def _build_dcell(self):
        print "build_dcell | dcell_k={} | dcell_n={}".format(comm.DCELL_K, comm.DCELL_N)

        self._hosts = {}     # (k+1)-tuple -> host name
        self._switches = {}  # (k+1)-tuple -> switch name
        self._nhost = 1
        self._nswitch = 1
        self._nswitch0, nswitch = comm.count_nodes()

        def build_helper(self, pref, n, level):
            if level == 0: # build DCell_0
                self._nswitch0 += 1
                switch_name0 = "s" + str(self._nswitch0)
                s0 = self._add_switch(switch_name0)
                for i in range(n):
                    id = str(pref + [i])
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
                build_helper(self, pref + [i], n, level - 1)

            for i in range(t[level - 1]):  # connect the DCell_(l-1)s
                for j in range(i + 1, g[level]):
                    n1 = str(pref + [i] + comm.tuple_id(j, level - 1, n))
                    n2 = str(pref + [j] + comm.tuple_id(i + 1, level - 1, n))
                    s1 = self._switches[n1]
                    s2 = self._switches[n2]
                    self._add_link(s1, s2)
                    print "(" + n1 + "," + s1 + ")...(" + n2 + "," + s2 + ")"

        t = []  # the number of servers in DCell_l
        g = []  # the number of DCell_(l-1)s in DCell_l
        t.append(comm.DCELL_N)
        g.append(1)
        for i in range(comm.DCELL_K):
            g.append(t[i] + 1)
            t.append(g[i + 1] * t[i])
        self._nswitch0 = t[comm.DCELL_K]
        pref = []
        build_helper(self, pref, comm.DCELL_N, comm.DCELL_K)  # construct DCell

    def _add_host(self, name):
        host_id = int(name[1:])
        ip, mac = comm.ip_to_str(host_id), comm.mac_to_str(host_id)  # ip/mac equals to host id
        return self.addHost(name, ip=ip, mac=mac)

    def _add_switch(self, name):
        return self.addSwitch(name, cls=comm.SWITCH_CLS)

    def _add_link(self, node1, node2):
        return self.addLink(node1, node2, bw=comm.LINK_BW)
