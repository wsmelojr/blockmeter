# Procedures to execute the Paillier Benchmark Test

* For each test case, start using a fresh instance of the PTB blockchain network. Create only the peer0.ptb.de, the cli0 and the orderer service containers (couchdb0 will also be started together peer0, but that is normal). That can be done executing this [script](blockchain/resetRestart.sh):

```console
./resetRestart.sh
```

* Limit the number of CPU cores used by the chaincode container. Notice we already limit the number of CPUs used by the endorser container (peer0.ptb.de) in the file [docker-compose-ptb.yaml](blockchain/docker-compose-ptb.yaml). We cannot use the same strategy with the chaincode container because the endorser creates it in runtime. However, that can be done by using the following command:

```console
docker update --cpus 4 99a064856650
```

where 4 is the number max CPU cores addmited to the container ID *99a064856650* (you must replace this ID by your container ID).

* Use the script [dockerstats.sh](blockchain/dockerstats.sh) to collect statistics of CPU usage from docker containers. The script waits for 3 containers ID as arguments (usually the chaincode, peer0 and its couchdb). Please check the comments in the script header for more information.

* Run the *prepare-morph-mp.py* program. The arguments must be the number of processes and threads (i.e. number of threads for each process) that will be used in the benchmark. This program will invoke the *registerMeter* chaincode and creates 100 meter IDs for each thread, in total of *100 \* nprocess \* nthreads* unique IDs. Here is an example about how to execute this program:

```console
python3 prepare-morph-mp.py 5 5
```

invokes the *registerMeter* chaincode 2,500 times, creating 2,500 unique meter IDs.

The same command can be used to inform a public key. You must do that when your test case involves homomorphic encryption. In this case, the command line will be something like:

```console
python3 prepare-morph-mp.py 5 5 666.pub 2048
```

where *666.pub* is the public key file name and *2048* is the key size in bits.

* Run the program [client-morph-mp.py](clients/client-morph-mp.py). The arguments must be exactly the same ones used with the program *prepare-morph-mp.py* previously executed. The difference is the parameter *mode*, which comes first and defines the benchmark according to the following table:

| Mode | Description                                                                                              |
|------|----------------------------------------------------------------------------------------------------------|
| 1    | The client submits the transaction and waits until it is confirmed in the ledger (default).              |
| 2    | The client asks for endorsement, but do not submit the transaction to the orderer.                       |
| 3    | The client asks for endorsement, submits the transaction to the orderer, but does not wait for a answer. |

The program *client-morph-mp.py* can be executed as follows:

```console
python3 client-morph-mp.py 3 5 5 666.pub 2048
```

which means the program sends transactions in mode 3, using *25* concurret threads, with homorphic encryption based on the public key *666.pub* of *2048* bits.

* Collect and analyse the benchmark data. The program *client-morph-mp.py* generates a .csv file for each concurrent thread. The .csv file has only 2 collums: the transaction start and end time. However, this information is enough to determine the number of complete transactions, the time elapsed during the transaction, the average throuput and also the latency.

You can join all the .csv files using *cat* command and work with them in a sheet processing software:

```console
cat *.csv > mytestcase.csv
```