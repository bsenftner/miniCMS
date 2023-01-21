#!/bin/bash
# expects one arg, the postgres container id
#
OUTFILE=dump_`date +%d-%m-%Y"_"%H_%M_%S`.gz
docker exec -t $1 pg_dump -U collectAdmin -c lawOfficeAC | gzip > ./$OUTFILE
echo "wrote $OUTFILE"
