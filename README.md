# The BlockMeter Experiment: A blockchain-base PKI for Smart Meters

This repository contains the implementation of the **BlockMeter Experiment**, developed at the Brazilian National Institute of Metrology, Quality, and Technology (Inmetro).

Research team:

* *Wilson S. Melo Jr. (wsjunior@inmetro.gov.br)*
* *Raphael C. S. Machado. (rcmachado@inmetro.gov.br)*

## What the BlockMeter Experiment is

The BlockMeter Experiment is a practical experiment that implements a blockchain-base PKI for smart meters. The BlockMeter uses ECDSA assymetric keys and creates a *blockchain digital asset* that replaces the need of a digital certificate. We assume that only a Registry Authority (RA) can insert digital assets into the ledger. On the other hand, any interested part can audit the blockchain entries and ask for a digital signature checking.

We adopt [Hyperledger Fabric 1.4 LTS](https://hyperledger-fabric.readthedocs.io/en/release-1.4/) as our blockchain platform. We configure a basic blockchain network which delivers the PKI elementary services.

We describe in the next sections the main aspects related to the Fabric blockchain network customizing, the chaincode development and the application client created to put all the stuff together.

## The customized blockchain network

We use a very simple Fabric blockchain network with two ordinary peers (one of them being an endorser) and the solo orderer service. We also use [couchdb](https://hyperledger-fabric.readthedocs.io/en/release-1.4/couchdb_tutorial.html) containers to improve the performance on storing the ledger state on each peer.

All the configuration files related to the blockchain network  are in the folder [tls](tls). The main files are:

* [configtx.yaml](tls/configtx.yaml): contains the network profile of our Fabric blockchain network.
* [crypto-config-ptb.yaml](tls/crypto-config-ptb.yaml): contains the MSP (Membership Service Provider) configuration. We generate all the digital certificates from it.
* [docker-compose-ptb.yaml](tls/docker-compose-ptb.yaml): contains the docker containers configuration. It extends the file [peer-base.yaml](tls/peer-base.yaml) which constitutes a template of standard configuration items.

If you are not used to the Hyperledger Fabric, we strongly recommend this [tutorial](https://hyperledger-fabric.readthedocs.io/en/release-1.4/build_network.html). It teachs in details how to create a basic Fabric network.

You can start BlockMeter Experiment network by executing the steps in the following subsections. All the commands must be executed into the folder blockchain.

### 1. Prepare the host machine

You need to install the **Hyperledger Fabric 1.4 LTS** basic software and [dependencies](https://hyperledger-fabric.readthedocs.io/en/release-1.4/prereqs.html). We try to make things simpler to you by providing a shell script that installs all these stuffs in a clean **Ubuntu 18.04 LTS** system. If you are using this distribution, our script works for you. If you have a different distribution, you can still try the script or you can customize it to work in your system.

Execute the [installation script](prerequirements/installFabric.sh):

```console
./installFabric.sh
```

**OBSERVATION**: you do not need to run the script as *sudo*. The script will automatically ask for your *sudo* password when necessary. That is important to keep the docker containers running with your working user account.

### 2. Generate the MSP artifacts

Before to execute this step, check if the environment variable FABRIC_CFG_PATH is properly defined. If it is not, uncomment the following line in the script [ptbMSP.sh](tls/mspPTB.sh).

```console
export FABRIC_CFG_PATH=$PWD
```

After, in the folder [tls](tls), execute the script:

```console
./mspPTB.sh
```

This script uses [configtx.yaml](tls/configtx.yaml) and [crypto-config-ptb.yaml](tls/crypto-config-ptb.yaml) to create the MSP certificates in the folder (tls/crypto-config). It also generates the genesis block file *ptb-genesis.block* and the channel configuration file *ptb-channel.tx*. Noticed that this script depends on the tools installed together with Fabric. The script *installFabric.sh* executed previously is expected to modify your $PATH variable and enable the direct execution of the Fabric tools. If this does not happen, try to fix the $PATH manually. The tools usually are located in the folder /$HOME/fabric_samples/bin.

### 3. Manage the docker containers

We use the **docker-compose** tool to manage all the docker containers in our network. It basically reads the docker-compose-ptb.yaml and creates/starts/stops all the containers or a specific group of containers. You can find more details in the [Docker Compose Documents](https://docs.docker.com/compose/).

In the folder [tls](tls), use the following command to start all the containers:

```console
docker-compose -f docker-compose-ptb.yaml up -d
```

The same tool can be used to stop the containers, just in case you need to stop the blockchain network for any reason. In a similar manner as done before, use the following command to stop all the containers:

```console
docker-compose -f docker-compose-ptb.yaml stop
```

If you need to reset and restart a completly new blockchain network, use the following script to remove containers and clean all dependencies:

```console
./teardown.sh
```

### 4. Create the Fabric channel and join the peers

The last step consists on creating a channel (in practice, the ledger among the peers) and join all the active peer on it. That can be done by executing the following script into the folder blockchain:

```console
./startPTB.sh
```

If you succeed in coming so far, the Hyperledger Fabric shall be running in your machine, with an instance of the PTB network profile. You can see information from the containers by using the following commands:

```console
docker ps
docker stats
```

## The fabpki chaincode

In this document, we assume you already know how to implement and deploy a chaincode in Fabric. If this is not your case, there is a [nice tutorial](https://hyperledger-fabric.readthedocs.io/en/release-1.4/chaincode4ade.html) that covers a lot of information about this issue. We strongly recomend you to check it before to continue.

If you already know everything you need about developing and deploying a chaincode, we can introduce the **fabpki** chaincode. It contains basic methods that provides elementary PKI services by using the [Golang ECDSA Library](https://golang.org/pkg/crypto/ecdsa/). The chaincode source is available [here](tls/fabpki/fabpki.go).

If you need to modify, compile and test the **fabpki** chaincode, be sure that you have the [Golang *shim* interface](https://godoc.org/github.com/hyperledger/fabric/core/chaincode/shim) properly installed in your machine. If you do not have it, you can install it by using the following command:

```console
go get -u github.com/hyperledger/fabric/core/chaincode/shim
```

### Shell commands to deal with a Fabric chaincode

Our blockchain network profile includes the client container *cli0* which is provided only to execute tests with the chaincode. The *cli0* is able to communicate with the blockchain network using the peer *peer0.ptb.de* as an anchor and so execute commands for installing, mantaining and testing the chaincode. These commands documentation can be find [here](https://hyperledger-fabric.readthedocs.io/en/release-1.4/commands/peerchaincode.html). We strongly recommend you read this documentation before continuing.

#### 1. Installing, instantiating and upgrading a chaincode

Use the **install** command to enable the chaincode execution for a given peer. In practice, you are making this peer an __endorser__. You must reexecute the install command every time you change the chaincode version.

```console
docker exec cli0 peer chaincode install -n fabpki -p github.com/hyperledger/fabric/peer/channel-artifacts/fabpki -v 1.0 --tls --cafile /etc/hyperledger/tlscacerts/tlsca.ptb.de-cert.pem
```

Use the **instantiate** command to instantiate the chaincode in a given channel. In practice, you are notifying the blockchain network that the chaincode exists. You also create a entry in the ledger with the chaincode hash.

```console
docker exec cli0 peer chaincode instantiate -o orderer.ptb.de:7050 -C ptb-channel -n fabpki -v 1.0 -c '{"Args":[]}' --tls --cafile /etc/hyperledger/tlscacerts/tlsca.ptb.de-cert.pem
```

Use the **upgrade** command to enable a new version of the chaincode. That is necessary for any chaincode that was already instantiated before. Notice that a upgraded chaincode need to be re-installed in each one of its endorser peers.

```console
docker exec cli0 peer chaincode upgrade -o orderer.ptb.de:7050 -C ptb-channel -n fabpki -v 1.0 -c '{"Args":[]}' --tls --cafile /etc/hyperledger/tlscacerts/tlsca.ptb.de-cert.pem
```

## The Client Application

The client application is a set of Python 3 modules that use the chaincode services provided by the blockchain network. They make use of the Python ECDSA Library (which implements the our cryptosystem) and the Fabric Python SDK.

You need to install some dependencies and libraries before geting the clients running properly. We described all the steps necessary to prepare your machine to do that.

### Get pip3

Install the Python PIP3 using the following command:

```console
sudo apt install python3-pip
```

### Get the ECDSA Python Library

The ECDSA Library implements the directives related to the Elliptic Curves algorithms. You can find more details [here](https://pypi.org/project/ecdsa/). Run the following command to install the ECDSA Library.

```console
pip3 install ecdsa
```

### Get the Fabric Python SDK

The [Fabric Python SDK](https://github.com/hyperledger/fabric-sdk-py) is not part of the Hyperledger Project. It is maintained by an independent community of users from Fabric. However, this SDK works fine, at least to the basic functionalities we need.

Recently, we have problems with broke interfaces that made our programs stoped of running. So we adopted the 0.8.0 version of the Python SDK (and the respective tag) as our "stable" version.

You need to install the Python SDK dependencies first:

```console
sudo apt-get install python-dev python3-dev libssl-dev
```

Finally, install the Python SDK using *git*. Notice that the repository will be cloned into the current path, so we recommend you install it in your $HOME directory. After cloning the repository, is necessary to checkout the tag associated to the version 0.8.0.

```console
cd $HOME
git clone https://github.com/hyperledger/fabric-sdk-py.git
cd fabric-sdk-py
git checkout tags/v0.8.0
sudo make install
```

### Configure the .json network profile
The Python SDK applications depend on a network profile encoded in a .json format. In this repository, this file the [ptb-network-tls.json](clients/ptb-network-tls.json) file. The network profile keeps the necessary credentials to access the blockchain network. You must configure this file properly every time that you create new digital certificates in the MSP:

* Open the [ptb-network.json](clients/ptb-network.json) in a text editor;
* Check for the entries called "private_key" on each organization. Notice that they points out to a file into the (../tls) directory that corresponds to the private key of each organization;
* Check the MSP file structure in your deployment and verify the correct name of the files that contain the private key;
* Modify the .json file with the correct name of the files.

### The Client Application modules

The Client Application includes the following modules:

* [keygen-ecdsa.py](clients/keygen-ecdsa.py): It is a simple Python script that generates a pair of ECDSA keys. These keys are necessary to run all the other modules.
* [register-ecdsa.py](clients/register-ecdsa.py): It invokes the *registerMeter* chaincode, that appends a new meter digital asset into the ledger. You must provide the respective ECDSA public key.
* [verify-ecdsa.py](clients/verify-ecdsa.py): It works as a client that verifies if a given digital signature corresponds to the meter's private key. The client must provide a piece of information and the respective digital signature. The client module will inform **True** for a legitimate signature and **False** in the opposite.