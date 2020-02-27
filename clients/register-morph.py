"""
    The Paillier Experiment - Register
    ~~~~~~~~~
    This module is necessary to register a meter in the blockchain. It
    receives the meter ID and the keysize defined to this meter. This
    module must be called before any other one related to insertion 
    and queries against the ledger.
        
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

#defines the chaincode version
cc_version = "1.0"

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
    try:
        pub_key = pickle.load(open(pub_key_file, "rb"))
        #generates de pub_key in string format
        pub_key_str = keysize + "," + str(pub_key.n) + "," + str(pub_key.g) + "," + str(pub_key.nsquare)
    except:
        print("Without a public key. We will continue as a plaintext.")
        pub_key_str = ""

    #creates a loop object to manage async transactions
    loop = asyncio.get_event_loop()

    #instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network.json")

    #get access to Fabric as Admin user
    admin = c_hlf.get_user('ptb.de', 'Admin')

    #query peer installed chaincodes, make sure the chaincode is installed
    response = loop.run_until_complete(c_hlf.query_installed_chaincodes(
        requestor=admin,
        peers=['peer0.ptb.de']
    ))

    print(response)

    #the Fabric Python SDK do not read the channel configuration, we need to add it mannually'''
    c_hlf.new_channel('ptb-channel')

    #shows the meter public key
    print("/",pub_key_str,"/")

    #invoke the chaincode to register the meter
    response = loop.run_until_complete(
        c_hlf.chaincode_invoke(requestor=admin, channel_name='ptb-channel', peers=['peer0.ptb.de'],
        args=[meter_id,pub_key_str], cc_name='fabmorph', cc_version=cc_version,
        fcn='registerMeter', cc_pattern=None))

    #so far, so good
    print(response)