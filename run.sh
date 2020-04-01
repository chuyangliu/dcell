#!/bin/sh

mn -c
chmod +x pox/ext/main.py pox/pox.py
cd ./pox/ext/ && ./main.py $1
