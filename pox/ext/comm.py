#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.node import OVSKernelSwitch

# DCell level to build and test
DCELL_LEVEL = 0
# number of hosts in a DCell_0
DCELL_N = 4
# data link bandwidth (Mbps)
LINK_BW = 100
# switch class
SWITCH_CLS = OVSKernelSwitch


def dcell_count(k, n):
    """Calculate total number of hosts and switches in a DCell.

    Args:
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0

    Returns:
        num_hosts (int): number of hosts in the DCell
        num_switches (int): number of switches in the DCell
    """
    if k == 0:
        return n, n + 1
    num_hosts, num_switches = n, 1
    for _ in range(0, k):
        num_switches *= num_hosts + 1
        num_hosts *= num_hosts + 1
    num_switches += num_hosts  # each host associated with one switch
    return num_hosts, num_switches


def mac_to_str(mac):
    """Convert a mac address integer to a string "XX:XX:XX:XX:XX:XX"."""
    mac_str = "%012x" % mac
    return ":".join(s.encode('hex') for s in mac_str.decode('hex'))
