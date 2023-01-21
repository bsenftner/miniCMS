#!/bin/bash
# expects two args, in this order:
# 1) filename of the gzipped postgres backup to restore
# 2) the postgres container id
#
# gunzip < $1 | docker exec -i $2 psql -U collectAdmin -d lawOfficeAC
#
gunzip < $1 | docker exec -i $2 psql -U collectAdmin lawOfficeAC 
echo "restored $1"
