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


def dcell_count():
    """Calculate total number of hosts and switches in current DCell.

    Returns:
        num_hosts (int): number of hosts in the DCell
        num_switches (int): number of switches in the DCell
    """
    num_hosts, num_switches = DCELL_N, 1

    if DCELL_K > 0:
        for _ in range(DCELL_K):
            num_switches *= num_hosts + 1
            num_hosts *= num_hosts + 1

    # each host associated with one switch
    num_switches += num_hosts

    return num_hosts, num_switches


def dcell_tuple_id(host_id):
    """Convert host id to its equivalent k+1 tuple representation.

    Args:
        host_id (int): Host id within range [1, num_hosts]

    Returns:
        tuple_id (tuple): k+1 tuple representation of the host id
    """
    tuple_id = [0,] * (DCELL_K + 1)
    n = DCELL_N

    for i in range(DCELL_K, -1, -1):
        if i == DCELL_K:
            tuple_id[i] = (host_id - 1) % n
        else:
            tuple_id[i] = (host_id - 1) / n
            n *= n + 1

    return tuple(tuple_id)


def dcell_host_id(tuple_id):
    """Convert k+1 tuple id to its equivalent host id.

    Args:
        tuple_id (tuple): k+1 tuple representation of the host id

    Returns:
        host_id (int): Host id (within range [1, num_hosts]) corresponding to the k+1 tuple id
    """
    host_id = 0
    n = DCELL_N

    for i in range(DCELL_K, -1, -1):
        if i == DCELL_K:
            host_id += tuple_id[i]
        else:
            host_id += tuple_id[i] * n
            n *= n + 1

    return host_id + 1
