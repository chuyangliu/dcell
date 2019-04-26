#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

import os
import sys
import time

import matplotlib
matplotlib.use("Agg")  # do not use any Xwindows backend
import matplotlib.pyplot as plt

from mininet.node import Controller
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

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


def testFaultTolerance():
    """Fault-tolerance test in Section 7.3 of the DCell paper."""
    SERVER_LOG = os.path.join(comm.DIR_LOG, "fault_server.log")
    CLIENT_LOG = os.path.join(comm.DIR_LOG, "fault_client.log")
    FIGURE = os.path.join(comm.DIR_FIGURE, "fault.png")
    DURATION = 160  # seconds

    if comm.DCELL_K != 1 or comm.DCELL_N != 4:
        print "Failed: require level-1 DCell with n=4"
        return

    # create net
    net = Mininet(topo=DCellTopo(tree=False), link=TCLink, controller=DCellController)
    net.start()
    print "Waiting controller setup..."
    time.sleep(5)
    print "\n[Fault-Tolerance Test]"

    # create results directory
    if not os.path.exists(comm.DIR_LOG):
        os.mkdir(comm.DIR_LOG)
    if not os.path.exists(comm.DIR_FIGURE):
        os.mkdir(comm.DIR_FIGURE)

    # start iperf server on host (4,3)
    print "Running iperf server..."
    net["h20"].cmd("iperf -s >{} 2>&1 &".format(SERVER_LOG))
    time.sleep(1)

    # start iperf client on host (0,0)
    print "Running iperf client (estimated duration: {} seconds)...".format(DURATION)
    net["h1"].cmd("iperf -c 10.0.0.20 -t {} -i 1 -y c >{} 2>&1 &"
                  .format(DURATION, CLIENT_LOG))

    # unplug link (0,3)-(4,0) at time 34s
    time.sleep(34)
    net.configLinkStatus("s4", "s17", "down")
    print "34s: (0,3)-(4,0) down"

    # replug link (0,3)-(4,0) at time 42s
    time.sleep(8)
    net.configLinkStatus("s4", "s17", "up")
    print "42s: (0,3)-(4,0) up"

    # shutdown (0,3) at time 104s
    time.sleep(62)
    net.configLinkStatus("s4", "s17", "down")
    net.configLinkStatus("s4", "s21", "down")
    print "104s: (0,3) down"
    time.sleep(60)

    # plot throughput
    throughputs = []
    with open(CLIENT_LOG, "r") as f:
        for line in f.readlines():
            throughputs.append(int(line.strip().split(",")[-1]) / 1e6)  # Mbps
    plt.plot(range(len(throughputs)), throughputs, "r")
    plt.xlabel("Time (second)")
    plt.ylabel("TCP Throughput (Mb/s)")
    plt.savefig(FIGURE)

    # stop net
    net.stop()


def testNetworkCapacity():
    """Network capacity test in Section 7.3 of the DCell paper."""
    SERVER_LOG = os.path.join(comm.DIR_LOG, "capacity_server_{}.log")
    CLIENT_LOG = os.path.join(comm.DIR_LOG, "capacity_client_{}_{}.log")
    FIGURE = os.path.join(comm.DIR_FIGURE, "capacity.png")
    DURATION = 800  # seconds
    DATA_SIZE = "250M"


    if comm.DCELL_K != 1 or comm.DCELL_N != 4:
        print "Failed: require level-1 DCell with n=4"
        return

    def test(tree):
        # create net
        net = Mininet(topo=DCellTopo(tree=tree), link=TCLink, controller=DCellController)
        net.start()
        print "Waiting controller setup..."
        time.sleep(5)
        print "\n[Network Capacity Test - {}]".format("Tree" if tree else "DCell")

        # create results directory
        if not os.path.exists(comm.DIR_LOG):
            os.mkdir(comm.DIR_LOG)
        if not os.path.exists(comm.DIR_FIGURE):
            os.mkdir(comm.DIR_FIGURE)

        # start iperf server on each host
        print "Running iperf server..."
        for i in range(1, 21):
            host_name = "h" + str(i)
            net[host_name].cmd("iperf -s >{} 2>&1 &".format(SERVER_LOG.format(i)))
        time.sleep(1)

        # start iperf client on each host
        print "Running iperf client (estimated duration: {} seconds)...".format(DURATION)
        for i in range(1, 21):
            for j in range(1, 21):
                if i != j:
                    host_name = "h" + str(i)
                    net[host_name].cmd("iperf -c 10.0.0.{} -n {} -i 1 -y c >{} 2>&1 &"
                                       .format(j, DATA_SIZE, CLIENT_LOG.format(i, j)))

        # wait client finish
        time.sleep(DURATION)

        # stop net
        net.stop()

    test(tree=False)


def main():
    # command-line args
    cli = len(sys.argv) >= 2 and sys.argv[1] == "cli"

    if cli:  # run Mininet CLI
        net = Mininet(topo=DCellTopo(tree=False), link=TCLink, controller=DCellController)
        net.start()
        print "Waiting controller setup..."
        time.sleep(3)
        CLI(net)
        net.stop()
    else:  # run tests
        testFaultTolerance()
        # testNetworkCapacity()
        print "\nFinished: please see directory \"figures\" for details\n"


if __name__ == "__main__":
    setLogLevel("info")
    main()
