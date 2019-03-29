#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import sys
import time

from mininet.node import Controller
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from comm import *
from topo import DCellTopo


class DCellController(Controller):
    """
    Run a POX controller for DCell routing in a separate process.
    Log location: /tmp/c0.log
    """
    def __init__(self, name):
        args = {
            "name": name,
            "command": "../pox.py",
            "cargs": (
                # "--verbose "
                "openflow.of_01 --port=%d "
                "openflow.discovery --link_timeout=1 "  # 1 sec
                "dcell_pox --dcell_level={} --dcell_n={}".format(DCELL_LEVEL, DCELL_N)
            )
        }
        Controller.__init__(self, **args)


def main():
    # command-line args
    cli = len(sys.argv) >= 2 and sys.argv[1] == "cli"

    # start a net
    net = Mininet(
        topo=DCellTopo(tree=False),
        link=TCLink,
        controller=DCellController
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
