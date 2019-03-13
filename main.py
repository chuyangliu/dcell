#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import time

from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from dcell import DCellController, DCellTopo


def main():
    net = Mininet(topo=DCellTopo(), link=TCLink, controller=DCellController, autoSetMacs=True)
    net.start()
    time.sleep(1)
    print "Testing network connectivity"
    net.pingAll()
    print "Testing bandwidth between h1 and h3"
    h1, h3 = net["h1"], net["h3"]
    net.iperf((h1, h3))
    # CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
