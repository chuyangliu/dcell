# DCell

[DCell][dcell-url] data center network structure.

## Hierarchy

```
run.sh   # main entrance: cleanup temp files and run main.py 
main.py  # setup the DCell network structure using Mininet, start a POX controller for DCell routing
pox      # POX library (version "dart": github.com/noxrepo/pox/tree/dart)
|- ext
|  |- dcell_pox.py  # POX controller for DCell routing
|  |- ...
|- ...
|- other lib files/directories
```

[dcell-url]: https://www.microsoft.com/en-us/research/publication/dcell-a-scalable-and-fault-tolerant-network-structure-for-data-centers/
