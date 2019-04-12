#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.node import OVSKernelSwitch

# DCell level to build and test
DCELL_K = 1
# number of hosts in a DCell_0
DCELL_N = 3
# data link bandwidth (Mbps)
LINK_BW = 100
# data link heartbeat timeout (seconds)
LINK_TIMEOUT = 1
# switch class
SWITCH_CLS = OVSKernelSwitch


def mac_to_str(mac):
    """Convert a mac address integer to a string "XX:XX:XX:XX:XX:XX"."""
    mac_str = "%012x" % mac
    return ":".join(s.encode('hex') for s in mac_str.decode('hex'))


def dcell_count(k, n):
    """Calculate total number of hosts and switches in current DCell.

    Args:
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0

    Returns:
        num_hosts (int): number of hosts in the DCell
        num_switches (int): number of switches in the DCell
    """
    num_hosts, num_switches = n, 1

    if k > 0:
        for _ in range(k):
            num_switches *= num_hosts + 1
            num_hosts *= num_hosts + 1

    # each host associated with one switch
    num_switches += num_hosts

    return num_hosts, num_switches


def dcell_tuple_id(k, n, host_id):
    """Convert host id to its equivalent k+1 tuple representation.

    Args:
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0
        host_id (int): Host id within range [1, num_hosts]

    Returns:
        tuple_id (list): k+1 tuple representation of the host id
    """
    tuple_id = [0,] * (k + 1)
    for i in range(k, -1, -1):
        if i == k:
            tuple_id[i] = (host_id - 1) % n
        else:
            tuple_id[i] = (host_id - 1) / n
            n *= n + 1
    return tuple_id


def dcell_host_id(k, n, tuple_id):
    """Convert k+1 tuple id to its equivalent host id.

    Args:
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0
        tuple_id (list): k+1 tuple representation of the host id

    Returns:
        host_id (int): Host id (within range [1, num_hosts]) corresponding to the k+1 tuple id
    """
    host_id = 0
    for i in range(k, -1, -1):
        if i == k:
            host_id += tuple_id[i]
        else:
            host_id += tuple_id[i] * n
            n *= n + 1
    return host_id + 1
