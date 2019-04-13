#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name

from mininet.node import OVSKernelSwitch

# whether run POX in debug mode
DEBUG_POX = False
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
# base value for IP addresses
IP_BASE = 10 << 24
# netmask
IP_MASK = 8


def mac_to_str(mac):
    """Convert a mac address integer to a string "XX:XX:XX:XX:XX:XX"."""
    mac_str = "%012x" % mac
    return ":".join(s.encode('hex') for s in mac_str.decode('hex'))


def ip_to_str(ip):
    """Convert a subnet IP address integer to its dot-decimal string."""
    ip += IP_BASE
    return "{}.{}.{}.{}/{}".format(
        (ip >> 24) & 0xFF, (ip >> 16) & 0xFF, (ip >> 8) & 0xFF, ip & 0xFF, IP_MASK)


def ip_to_mac(ip):
    """Convert a dot-decimal IP string to its mac address string."""
    ip_int = 0
    for i, val in enumerate(ip.split(".")):
        ip_int += int(val) << (24 - 8 * i)
    return mac_to_str(ip_int - IP_BASE)


def count_nodes(k=DCELL_K, n=DCELL_N):
    """Count total number of hosts and switches in a given DCell.

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


def count_dcells(k=DCELL_K, n=DCELL_N):
    """Count number of DCell_(k-1) in a given DCell.

    Args:
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0

    Returns:
        num_dcells (int): number of DCell_(k-1) in the DCell
    """
    num_dcells, num_hosts = 1, n
    for _ in range(k):
        num_dcells = num_hosts + 1
        num_hosts = num_dcells * num_hosts
    return num_dcells


def tuple_id(host_id, k=DCELL_K, n=DCELL_N):
    """Convert host id to its equivalent k+1 tuple representation.

    Args:
        host_id (int): Host id within range [1, num_hosts]
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0

    Returns:
        tuple_id (list): k+1 tuple representation of the host id
    """
    num_dcells = [1,] * (k + 1)
    num_hosts = [n,] * (k + 1)
    for i in range(k - 1, -1, -1):
        num_dcells[i] = num_hosts[i + 1] + 1
        num_hosts[i] = num_dcells[i] * num_hosts[i + 1]

    tuple_id = [0,] * (k + 1)
    host_id -= 1
    for i in range(k + 1):
        if i == k:
            tuple_id[i] = host_id % num_hosts[i]
        else:
            tuple_id[i] = host_id / num_hosts[i + 1]
            host_id %= num_hosts[i + 1]

    return tuple_id


def host_id(tuple_id, k=DCELL_K, n=DCELL_N):
    """Convert k+1 tuple id to its equivalent host id.

    Args:
        tuple_id (list): k+1 tuple representation of the host id
        k (int): Level of DCell to calculate
        n (int): Number of hosts in a DCell_0

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
