# DCell

![][badge-python] [![][badge-mininet]][src-mininet] [![][badge-pox]][src-pox]

[DCell][dcell-url] data center network structure implemented with software-defined networking (SDN).

## Installation <!-- omit in toc -->

1. [Install Mininet][mininet-download]. Recommend native installation from source on Ubuntu:

    ```
    $ git clone https://github.com/mininet/mininet.git
    $ cd mininet
    $ git checkout -b 2.3.0d5
    $ cd ..
    $ mininet/util/install.sh -a
    ```

2. Install libraries:

    ```
    $ pip install -r requirements.txt
    ```

3. Run DCell benchmarks

    ```
    $ sudo ./run.sh [cli]
    ```

## Structure <!-- omit in toc -->

```
run.sh  # main entrance: run DCell benchmarks
tools   # tool scripts
pox     # POX library
|- ext
|  |- comm.py              # DCell configurations and helper functions
|  |- main.py              # build network, start POX controller, and run benchmarks
|  |- topo.py              # topology for DCell and the two-level tree
|  |- dcell_controller.py  # POX controller for DCell network routing
|  |- tree_controller.py   # POX controller for tree network routing
|- ...
|- other POX library files
```

## Introduction

DCell is a novel data center network structure to alleviate problems in traditional tree structures. It uses redundant links to achieve fault-tolerance. It leverages a recursively-defined structure to eliminate the root switch bottleneck commonly seen in a tree-based structure, increasing network capacity. It's also scalable as it supports hundreds of thousands or even millions of servers with low wiring costs and it's easy to add more servers to an operational network.

The goal of the project is to reproduce the two experiments conducted in the DCell paper, demonstrating the fault-tolerance and high network capacity of DCell data center network structure. Benefit from software-defined networking, we can fast build the network structure, implement routing algorithms, and perform throughput tests.

Table of Contents:

- [Introduction](#introduction)
  - [DCell Summary](#dcell-summary)
    - [DCell Network Structure](#dcell-network-structure)
    - [DCell Routing](#dcell-routing)
      - [Routing without Failure](#routing-without-failure)
      - [Fault-Tolerant Routing](#fault-tolerant-routing)
  - [Experiments](#experiments)
    - [Fault-Tolerance](#fault-tolerance)
    - [Network Capacity](#network-capacity)
    - [Implementation](#implementation)
  - [Results](#results)
    - [Fault-Tolerance](#fault-tolerance-1)
    - [Network Capacity](#network-capacity-1)

### DCell Summary

In this part, we briefly summarize the DCell network structure and its routing algorithms. Please refer to the paper for more details.

#### DCell Network Structure

DCell network structure is recursively-defined. The smallest part in the structure is a DCell_0, where *n* servers directly connected to a mini-switch. A level-1 DCell, denoted as DCell_1, can then be constructed using several DCell_0. Similarly, a DCell_2 can be built with multiple DCell_1, so on and so forth.

#### DCell Routing

##### Routing without Failure

The routing path between two hosts when no failures occur is also created recursively. To build the path from the source host to the destination host, the first step is to find the highest DCell level *k* that separates the two hosts, and get the unique link spanning the two DCell_k each host belongs to respectively. The link has two end nodes. One is nearer to the source host (node A). The other is nearer to the destination host (node B). Then, the problem is converted to two sub-problems, namely how to find the path from the source host to node A, and the path from node B to the destination host, which can be solved recursively.

##### Fault-Tolerant Routing

There are three possible kinds of failures in the network: link failure which means the connectivity between two servers is failed but the two end servers themselves can work properly; node failure which means a whole server or switch is down; rack failure which means all the servers in a rack fail.

DCell use **local re-route** and **local link-state** to cope with node/link failures. Generally, if a link between host A and host B is broken, a proxy node will first be selected in another DCell at the same level as the failed link. Then, the packet is directed from the source host to the proxy, and then from the proxy to the destination host. These two sub-paths can be built recursively as before. If a whole rack fails (generally a DCell_0 is a rack), DCell uses **jump-up** to direct the packet to a higher-level DCell to bypass the failed rack.

### Experiments

There are two experiments in the paper, testing DCell network structure's fault-tolerance and network capacity, respectively.

#### Fault-Tolerance

The first experiment tests DCell's fault-tolerance based on a DCell_1 with 4 hosts in each DCell_0. Initially when there are no failures, [0,0] communicates with [4,3] through path [0,0]=>[0,3]=>[4,0]=>[4,3]. To test link failures, the authors unplug the link ([0,3], [4,0]) at time 34s and then re-plug it at time 42s. At time 104s, they shutdown [0,3] to test node failures. Rack failures are not tested in this experiment.
After both failures, the routing path from [0,0] to [4,3] changes to [0,0]=>[1,0]=>[1,3]=>[4,1]=>[4,3]. After the re-plug at 42s, the route path changes back to the original one. During the whole process, the TCP throughput between [0,0] and [4,3] is measured every second.

#### Network Capacity

The second experiment tests DCell's network capacity, which uses the same DCell structure as the first experiment. At the beginning, each one of the 20 servers establishes a TCP connection with the remaining 19 servers respectively, creating 380 connections in total. Then, each TCP connection simultaneously sends 5 GB data, creating essentially an all-to-all traffic pattern (e.g., reduce phase in MapReduce). The aggregated throughput of all the connections is measured every second. Besides the DCell structure, a two-level tree structure is also tested for the same connections and traffic pattern. In the tree structure, the five DCell0s are connected to a single root switch.

#### Implementation

Due to limited resources and time, we were not able to implement the DCell routing algorithms in a kernel-mode driver of the operating system like what the paper did. Instead, we leveraged software-defined networking (SDN) for fast prototyping the network structure and routing methods.

The network structures (i.e., the DCell_1 and the two-level tree used in the experiments) were built on Mininet, while the routing algorithms were implemented in a single POX controller. For the DCell structure, as we can obtain a global view of the states of switches and links in the POX controller, we built the forwarding tables of switches for each pair of hosts once all the switches were connected to the controller. For the tree structure, we implemented each switch as a normal layer-2 learning switch.

Mininet supports plugging and re-plugging links, which triggers `LinkEvent` of the POX controller. In the handler of `LinkEvent`, we implemented local-reroute to find alternative routing paths. Node failures were simulated by unplugging all the links connected to the failed node. We didn't handle rack failures as they were not tested in the paper's experiments.

One limitation of Mininet is that the hosts cannot route packets. However, in DCell, they must be able to route packets for the structure to work. To address this problem, we paired each host in a DCell with a switch and let the switch to do the routing for the host, as shown in the figure below:

![][img-dcell1-without-host-routing]

Due to limited compute power of our machines, we lowered our link bandwidth and the size of datasets. For both the experiments, we limited the bandwidth of the links to 100 Mbps instead of 1000 Mbps used in the paper to generate more stable results. For the network capacity experiment, we sent 250 MB data in each connection instead of 5 GB.

The official recommended way to use Mininet is to install its VM image and run it in VirtualBox or other virtualization platforms. We found the experiment results on the VM extremely unstable so we decided to run our experiments on AWS (i.e., a m4.xlarge instance), which gave us more consistent results.

### Results

#### Fault-Tolerance

During the first experiment, we measured the TCP throughput between [0,0] and [4,3] every second, and performed the plugging/unplugging operations the same as those in the paper. The figure below shows the results of our experiments compared to the paper.

![][img-fault-tolerance-compare]

From both graphs in the above figure we can see that at 34s, because of the link failure, the throughput dropped down sharply. After a few seconds, a new route was established so the throughput came back to normal. Similar for the node failure at 104s.

There are two main differences between the two results in the figure. The first is that the TCP throughput is reduced by approximately a factor of 10 in our results since we chose to use 100 Mbps links instead of 1000 Mbps used in the paper. The other difference is that node failures took more time to recover in the paper's results, whereas it took roughly the same time as link failures in our experiment. The reason is that node failures were simulated by multiple link failures in our implementation, so the time required before a failure can be detected was the same for link failures and node failures. In the paper's experiment, node failures were detected 5 times slower than link failures. That's why it took different time to react to these failures in the paper's results.

#### Network Capacity

In the second experiment, the aggregated throughput of all 380 TCP connections was measured every second. The figure below shows our results compared to the paper's.

![][img-network-capacity-compare]

From both graphs in the above figure we can find that DCell structure finished the workload nearly 2 times faster than the two-level tree structure. The reason is that in the tree structure, the root switch (a bottleneck in the structure) became congested after the hosts kept sending data to each other for a while, which reduced the aggregated throughput sharply. The workload in DCell was more balanced than that in the two-level tree and thus alleviate the problem.

There are two main differences between the two graphs in the figure. The first is that our aggregated throughput is lower than the paper's. The reason is the same as the previous experiment in that we use 100 Mbps links instead of 1000 Mbps. Another difference is the initial aggregated throughput of the tree structure. In the paper's results, it remains at a low level since the beginning of the experiment. However, in our results, it stays at a high level at the beginning and drops instantly at about 100s. We believe the reason is that before 100s, the root switch in our machine hadn’t reached its bottleneck yet. After the traffic accumulated at the queues of the root switch, it finally became conjected at 100s and thus lowered the aggregated throughput.

## References <!-- omit in toc -->

1. A. Greenberg, J. Hamilton, D. A. Maltz, and P. Patel, "The Cost of a Cloud: Research Problems in Data Center Networks," ACM SIGCOMM Comput. Commun. Rev., vol. 39, no. 1, p. 68, Dec. 2008.
2. C. Guo, H. Wu, K. Tan, L. Shi, Y. Zhang, and S. Lu, "DCell: A Scalable and Fault-Tolerant Network Structure for Data Centers," in Proceedings of the ACM SIGCOMM 2008 conference on Data communication - SIGCOMM ’08, 2008, p. 75.
3. C. Guo et al., "BCube: A High Performance, Server-centric Network Architecture for Modular Data Centers," ACM SIGCOMM Comput. Commun. Rev., vol. 39, no. 4, p. 63, Aug. 2009.
4. R. Niranjan Mysore et al., "PortLand: A Scalable Fault-Tolerant Layer 2 Data Center Network Fabric," in Proceedings of the ACM SIGCOMM 2009 conference on Data communication - SIGCOMM ’09, 2009, p. 39.
5. D. Kreutz, F. M. V. Ramos, P. Esteves Verissimo, C. Esteve Rothenberg, S. Azodolmolky, and S. Uhlig, "Software-Defined Networking: A Comprehensive Survey," Proc. IEEE, vol. 103, no. 1, pp. 14–76, Jan. 2015.
6. N. McKeown et al., "OpenFlow: Enabling Innovation in Campus Networks," ACM SIGCOMM Comput. Commun. Rev., vol. 38, no. 2, p. 69, Mar. 2008.
7. Open Networking Foundation (ONF), "OpenFlow Switch Specification," Dec. 2009. [Online]. Available: https://www.opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf

## License <!-- omit in toc -->

See the [LICENSE](./LICENSE.md) file for license rights and limitations.

[badge-python]: https://img.shields.io/badge/python-2.7-blue.svg
[badge-mininet]: https://img.shields.io/badge/Mininet-2.3.0d5-blue.svg
[badge-pox]: https://img.shields.io/badge/POX-dart-blue.svg

[src-mininet]: https://github.com/mininet/mininet/tree/2.3.0d5
[src-pox]: https://github.com/noxrepo/pox/tree/dart

[dcell-url]: https://www.microsoft.com/en-us/research/publication/dcell-a-scalable-and-fault-tolerant-network-structure-for-data-centers/

[mininet-download]: http://mininet.org/download/

[img-dcell1-without-host-routing]: plots/dcell1_without_host_routing.png
[img-fault-tolerance-compare]: plots/fault_tolerance_comparison.png
[img-network-capacity-compare]: plots/network_capacity_comparison.png
