#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import os
import sys
import time

from mininet.node import Controller
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import matplotlib.pyplot as plt

import comm
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
                "{} "
                "openflow.of_01 --port=%d "
                "openflow.discovery --link_timeout={} "
                "controller"
                .format("--verbose log.level --DEBUG" if comm.DEBUG_POX else "", comm.LINK_TIMEOUT)
            )
        }
        Controller.__init__(self, **args)


def testFaultTolerance(net):
    """Fault-tolerance test in Section 7.3 of the DCell paper."""
    IPERF_SERVER_LOG = os.path.join(comm.DIR_RESULTS, "fault_iperf_server.log")
    IPERF_CLIENT_LOG = os.path.join(comm.DIR_RESULTS, "fault_iperf_client.log")
    FIGURE = os.path.join(comm.DIR_RESULTS, "fault_figure.png")
    DURATION = 160  # seconds

    print "\n[Fault-Tolerance Test]"

    if comm.DCELL_K != 1 or comm.DCELL_N != 4:
        print "Failed: require level-1 DCell with n=4"
        return

    # create results directory
    if not os.path.exists(comm.DIR_RESULTS):
        os.mkdir(comm.DIR_RESULTS)

    # start iperf server on node (4,3)
    print "Running iperf server..."
    net["h20"].cmd("iperf -s >{} 2>&1 &".format(IPERF_SERVER_LOG))
    time.sleep(1)

    # start iperf client on node (0,0)
    print "Running iperf client (estimated duration: {} seconds)...".format(DURATION)
    net["h1"].cmd("iperf -c 10.0.0.20 -t {} -i 1 -y c >{} 2>&1 &"
                  .format(DURATION, IPERF_CLIENT_LOG))

    # unplug link (0,3)-(4,0) at time 34s
    time.sleep(34)
    net.configLinkStatus("h4", "h17", "down")
    print "34s: (0,3)-(4,0) down"

    # replug link (0,3)-(4,0) at time 42s
    time.sleep(8)
    net.configLinkStatus("h4", "h17", "up")
    print "42s: (0,3)-(4,0) up"

    # shutdown (0,3) at time 104s
    time.sleep(62)
    net.configLinkStatus("h4", "h17", "down")
    net.configLinkStatus("h4", "h21", "down")
    print "104s: (0,3) down"
    time.sleep(60)

    # plot throughput
    throughputs = []
    with open(IPERF_CLIENT_LOG, "r") as f:
        for line in f.readlines():
            throughputs.append(int(line.strip().split(",")[-1]) / 1e6)  # Mbps
    plt.plot(range(len(throughputs)), throughputs, "r")
    plt.xlabel("Time (second)")
    plt.ylabel("TCP Throughput (Mb/s)")
    plt.savefig(FIGURE)
    print "Finished: please see directory \"results\" for details"

    print ""


def main():
    # command-line args
    cli = len(sys.argv) >= 2 and sys.argv[1] == "cli"

    # start a net
    net = Mininet(topo=DCellTopo(), link=TCLink, controller=DCellController)
    net.start()

    # wait controller starts
    print "Waiting controller setup..."
    time.sleep(5)

    if cli:  # run Mininet CLI
        CLI(net)
    else:  # run tests
        testFaultTolerance(net)

    # stop net
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
