"""
    The Paillier Experiment - Multiprocessing Prepare
    ~~~~~~~~~
    This module is part of the multiprocessing client benchmark. It prepare the test
    by registering 100 unique meter IDs for each individual thread. For instance, with
    you run the benchmark with 10 processes and 10 threads, this bechmark will create
    10*10*100 = 10000 unique IDs. We need that to prevent that our concurrent 
    transactions creates key collision (to learn more about this, I recommend the 
    following text: 
    https://medium.com/@gatakka/how-to-prevent-key-collisions-in-hyperledger-fabric-chaincode-303700716733).
    
    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""
import sys
sys.path.insert(0, "..")
import math
import random

import phe.encoding
from phe import paillier

import time
import array as arr
from hfc.fabric import Client as client_fabric
import asyncio

import json
import pickle

#defines the chaincode version
cc_version = "1.0"

if __name__ == "__main__":
    """The main program starts here. You need to inform the requested number of processes
    and threads. Also, if the meters shall work with homomorphic encryption, you must
    inform the public key and its size in bits.

    The program will generate 100 unique meter IDs for each thread. After, it invokes the
    chaincode registerMeter method, registering the ID in the ledger.    
    """
    #test if we have correct arguments
    if not (len(sys.argv) == 3 or len(sys.argv) == 5):
        print("Usage:",sys.argv[0],"<nprocesses> <nthreads> [<pubkey> <kbits>]")
        exit(1)

    #get the number of threads and process
    nprocesses = int(sys.argv[1])
    nthreads = int(sys.argv[2])
    kbits = "0"

    #treats the public key (if it was provided)
    if len(sys.argv) == 5:     
        try:
            #try to retrieve the public key
            pub_key = pickle.load(open(sys.argv[3], "rb"))
            kbits = sys.argv[4]
            pub_key_str = kbits + "," + str(pub_key.n) + "," + str(pub_key.g) + "," + str(pub_key.nsquare)

            #generates a encrypted initial value (this value is zero)
            encrypted_initial = str(pub_key.raw_encrypt(0))

        except:
            print("Invalid public key:",sys.argv[3])
            exit(1)
    else:
        #inform that we work with plaintext measurements.
        print("Without a public key. Measurements will be considered as plaintext.")
        pub_key = None
        pub_key_str = ""
        encrypted_initial = ""

    #instantiate the Fabric SDK client (ptb-network.json is our network profile)
    c_hlf = client_fabric(net_profile="ptb-network.json")
    #get access to Fabric as Admin user
    admin = c_hlf.get_user('ptb.de', 'Admin')
    #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
    c_hlf.new_channel('ptb-channel')

    #creates a loop object to manage async transactions
    loop = asyncio.get_event_loop()

    #we will create 100 meter IDs for each thread. So we need to multiple the following
    #operation: nprocess * nthreads * 1000
    for i in range(nprocesses):
        for j in range(nthreads):
            for k in range(100):
                #creates an unique meter ID
                meter_id = str(i * 10000 + j * 100 + k)

                #show the progress...
                print("Inserting meter ID " + meter_id + "...")

                #the chaincode calls 'insertMeasurement'. The transaction uses the meter ID for
                #inserting the new measurement. User admin is used. 
                loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                        peers=['peer0.ptb.de'],args=[meter_id,pub_key_str],
                        cc_name='fabmorph',cc_version=cc_version,fcn='registerMeter'
                        ))

                #does the register of the new meter_id
                #c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                #        peer_names=['peer0.ptb.de'],args=[meter_id,pub_key_str,encrypted_initial],
                #        cc_name='fabmorph',cc_version=cc_version,fcn='registerMeter',mode=3)
            #time.sleep(1)
                
    #log message
    print("Meters dataset was created with success!")
