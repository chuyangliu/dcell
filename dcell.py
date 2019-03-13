#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.topo import Topo
from mininet.node import Controller, OVSKernelSwitch


class DCellController(Controller):
    """Log to /tmp/c0.log"""
    def __init__(self, name="c0", cdir=".", command="./pox/pox.py",
                 cargs="--verbose openflow.of_01 --port=%d misc.of_tutorial", **kwargs):
        Controller.__init__(self, name, cdir=cdir, command=command, cargs=cargs, **kwargs)


class DCellTopo(Topo):
    def build(self, level=1, link_bw=100, switch_cls=OVSKernelSwitch):
        h1 = self.addHost("h1")
        h2 = self.addHost("h2")
        h3 = self.addHost("h3")
        s1 = self.addSwitch("s1", cls=switch_cls)
        self.addLink(s1, h1, bw=link_bw)
        self.addLink(s1, h2, bw=link_bw)
        self.addLink(s1, h3, bw=link_bw)
