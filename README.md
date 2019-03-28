# DCell

[DCell][dcell-url] data center network structure.

## Hierarchy

```
run.sh   # main entrance: cleanup temp files and run main.py 
main.py  # setup the DCell network structure using Mininet, start a POX controller for DCell routing
pox      # POX library
|- ext
|  |- dcell_pox.py  # POX controller for DCell routing
|  |- ...
|- ...
|- other lib files/directories
```

## Dependencies

- [Mininet (2.3.0d5)](https://github.com/mininet/mininet/tree/2.3.0d5)
- [POX (dart)](https://github.com/noxrepo/pox/tree/dart)

[dcell-url]: https://www.microsoft.com/en-us/research/publication/dcell-a-scalable-and-fault-tolerant-network-structure-for-data-centers/
