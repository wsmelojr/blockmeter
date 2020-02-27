"""
    The Paillier Experiment - Client (simple)
    ~~~~~~~~~
    This module as a single thread client that collect measurements
    from the OPCUA server and inserts encrypted measurements. 
    It does that continually, and the developer can choose between 
    a fix sleep time or a keypress from the user to continue 
    generating measurements.
        
    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""

import sys
sys.path.insert(0, "..")
import math

import phe.encoding
from phe import paillier

import time
import array as arr
from opcua import Client as client_opcua
from hfc.fabric import Client as client_fabric
import asyncio

import json
import pickle

if __name__ == "__main__":

    #test if the meter ID was informed as argument
    if len(sys.argv) != 3:
        print("Usage:",sys.argv[0],"<meter id> <keysize>")
        exit(1)        

    #get the meter ID
    meter_id = sys.argv[1]
    keysize = sys.argv[2]

    #format the name of the expected public key
    pub_key_file = meter_id + ".pub"

    #try to retrieve the public key
    pub_key = pickle.load(open(pub_key_file, "rb"))

    #instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network.json")
    #defines the chaincode version
    cc_version = "1.0"

    #instantiate the opcua client
    c_opcua = client_opcua("opc.tcp://localhost:4840/freeopcua/server/")

    try:
        #get access to Fabric as Admin user
        admin = c_hlf.get_user('ptb.de', 'Admin')
        #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
        c_hlf.new_channel('ptb-channel')

        #creates a loop object to manage async transactions
        loop = asyncio.get_event_loop()

        #generates de pub_key in string format
        pub_key_str = keysize + "," + str(pub_key.n) + "," + str(pub_key.g) + "," + str(pub_key.nsquare)

        #connect to the opcua server
        c_opcua.connect()
        #opcua client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
        root = c_opcua.get_root_node()
        #print shows what is happening
        print("OPC-UA Objects node is: ", root)

        #creates a accumulator to store the consumption locally
        local_consumption = 0
        read_control = 1

        while True:
            #gets the measurement sample from opcua server
            sample = root.get_child(["0:Objects", "2:MyObject", "2:System Load"])
            
            #print shows what is happening
            print("Sampled measurement: ", sample.get_value())

            #inserts the individual measurement into var param
            measurement = int(sample.get_value() * 10)

            encrypted = str(pub_key.raw_encrypt(measurement))

            #invoke the LR chaincode... 
            print("Invoking insertMeasurement chaincode... ", encrypted)
                
            #the chaincode calls 'insertMeasurement'. The transaction uses the meter ID for
            #inserting the new measurement. User admin is used. 
            response = loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                        peers=['peer0.ptb.de'],args=[meter_id,encrypted],
                        cc_name='fabmorph',cc_version=cc_version,fcn='insertMeasurement'
                        ))
            #let's see what we did get...
            print(response)

            #increases the accumulator
            local_consumption += measurement

            #so far, so good
            print("Insertion OK, getting next measurement (",local_consumption,")")

            #use this block of code to wait a little (we define our sampling rate)
            #or to ask for a key press from the user
            #time.sleep(5)
            input("Press ENTER to continue inserting measurements...")

    finally:
        #only opcua client need to be disconnected
        c_opcua.disconnect()