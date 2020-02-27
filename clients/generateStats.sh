#!/bin/bash
############################################################################
# The Paillier Experiment - PTB
#
# This script collects statistics related to CPU usage of until 3 containers.
# They usually are the chaincode container (that is created in runtime and 
# usually has a composed name with the chaincode name), the endorser container
# (where the chaincode was installed) and the couchdb container associated with
# the endorser.
#
# The script output is a table with 3 collumns showing the CPU usage curve.
#
# @author: Wilson S. Melo - Inmetro
# @date Mar/2019
############################################################################

#test if we have the csv file as parameter
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <stat file> <CPU|TRS>" >&2
  exit 1
fi

if [ "$2" = "CPU" ]; then
    echo "Dealing with CPU statistics..."

    c_chain=`awk '{ total += $1; count++ } END { print total/count }' $1`
    c_peer=`awk '{ total += $2; count++ } END { print total/count }' $1`
    c_db=`awk '{ total += $3; count++ } END { print total/count }' $1`

    echo "- chaincode(%) = "$c_chain
    echo "- endorser(%) = "$c_peer
    echo "- couchdb(%) = "$c_db

    exit 0
fi

if [ "$2" = "TRS" ]; then
    echo "Dealing with transactions statistics..."

    tmin=`awk -F, '{print $1}' $1 | sort -n | head -1`
    tmax=`awk -F, '{print $2}' $1 | sort -n | tail -1`
    count=`awk -F, '{print $2}' $1 | wc -l`
    ttime=`echo "$tmin $tmax" | awk '{print $2-$1}'`

    latency=`awk -F, '{print $2 - $1}' $1 | awk '{ total += $1; count++ } END { print total/count }'`
    throughput=`echo "$count $ttime" | awk '{print $1/$2}'`

    echo "- elapsed time(s) = "$ttime
    echo "- latency(s) = "$latency
    echo "- throughput(tps) = "$throughput

    exit 0
fi

echo "I don't know how to generate statistics to "$2