#!/bin/bash
############################################################################
# The Paillier Experiment - PTB
#
# This script automatizes all the steps necessary to run our benchmark test.
# It will need to be revised every time you make any change in the repository
# to be sure that it continues working.
# 
# Before starting, remeber that the script deletes any previous .cvs and 
# .stat files. So, before executing any new benchmark round, be careful to 
# make the backup of any statistic information generated in the previous 
# tests.
#
# @author: Wilson S. Melo - Inmetro
# @date Apr/2019
############################################################################

#test if we have the csv file as parameter
if ![ "$#" = 3 -o "$#" = 5 ]; then
  echo "Usage: $0 <mode> <nprocesses> <nthreads> [<pubkey> <kbits>]" >&2
  exit 1
fi

#assign variables to make things easier
TEST_MODE=$1
N_PROCESS=$2
N_THREADS=$3

if [ "$#" = 5 ]; then
  PUB_KEY=$4
  KEY_SIZE=$5
else
  PUB_KEY=""
  KEY_SIZE=""
fi

#a clear screen before start...
clear
#a screen to make things to seem serious...
cat benchmark.screen

#log information we got in the parameters
echo "The required configuration was:"
echo "- Execution mode: "$TEST_MODE
echo "- Number of concurrent processes: "$N_PROCESS
echo "- Number of threads per process: "$N_THREADS
if [ "$#" = 5 ]; then
  echo "- Public key file: "$PUB_KEY
  echo "- Key size: "$KEY_SIZE
else
  echo "- No cryptographic keys (plaintext) "
fi
echo

#asks for the user confirm (need to press Y or N)
while true; do
    read -p "ARE YOU READY TO CONTINUE? (Y/N) " yn
    case $yn in
        [Yy]* ) break;;
        [Nn]* ) exit 0;;
        * ) echo "Please answer yes (Y) or no (N).";;
    esac
done

#by assuming we are in the clients directory, we need to go to the blockchain directory
cd ../tls

#get us a fresh blockchain instance
./resetRestart.sh

#back to the clients directory...
cd ../clients

#remove any previous stats
rm -f *.csv *.stats

#prepare blockchain by inserting all the meters we need
python3 prepare-morph-mp.py $N_PROCESS $N_THREADS $PUB_KEY $KEY_SIZE

#get ledger status before executing benchmark
../blockchain/ledgerstats.sh > ledger-before.stats

#execute benchmark
python3 client-morph-mp.py $TEST_MODE $N_PROCESS $N_THREADS $PUB_KEY $KEY_SIZE

#get ledger status immediately after executing benchmark
../blockchain/ledgerstats.sh > ledger-after.stats

#generates TRS statistics from .csv files
cat *.csv > transactions.stats

#computes statistics from transactions
./generateStats.sh transactions.stats TRS

#computes statistics from CPU
./generateStats.sh cpu.stats CPU

#show ledger status before and after the benchmark
echo "The ledger status before the benchmark"
cat ledger-before.stats
echo "The ledger status IMMEDIATLY after the benchmark"
cat ledger-after.stats

#remove all the csv to keep the house clean
rm -f *.csv
