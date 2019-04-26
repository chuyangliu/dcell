# DCell

![][badge-python] [![][badge-mininet]][src-mininet] [![][badge-pox]][src-pox]

[DCell][dcell-url] data center network structure implemented with software-defined networking (SDN).

## Installation

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

## Structure

```
run.sh  # main entrance: run DCell benchmarks
tools   # tool scripts
pox     # POX library
|- ext
|  |- main.py        # build DCell structure, start a POX controller for DCell routing
|  |- topo.py        # DCell topology class
|  |- controller.py  # POX controller for DCell routing
|  |- comm.py        # DCell configurations and helper functions
|- ...
|- other POX library files
```

## License

See the [LICENSE](./LICENSE) file for license rights and limitations.

[badge-python]: https://img.shields.io/badge/python-2.7-blue.svg
[badge-mininet]: https://img.shields.io/badge/Mininet-2.3.0d5-blue.svg
[badge-pox]: https://img.shields.io/badge/POX-dart-blue.svg

[src-mininet]: https://github.com/mininet/mininet/tree/2.3.0d5
[src-pox]: https://github.com/noxrepo/pox/tree/dart

[dcell-url]: https://www.microsoft.com/en-us/research/publication/dcell-a-scalable-and-fault-tolerant-network-structure-for-data-centers/

[mininet-download]: http://mininet.org/download/
