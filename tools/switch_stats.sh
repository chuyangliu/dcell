#!/bin/sh
#
# Dump switch states and flow entries.
#

echo "[Overview]"
ovs-ofctl show $1

echo "\n[Flows]"
ovs-ofctl dump-flows $1
