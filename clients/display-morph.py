"""
    The Paillier Experiment - Display
    ~~~~~~~~~
    This module works like a meter display, by querying the blockchain
    ledger and retriving consumption information. He can be seen as a
    client application.

    We assume that this module have access to the meter's Paillier
    private key. That is necessary to decrypt the encrypted measurement
    information.

    Although we are invoking the getConsumption chaincode, such call works
    as a query, since it does not modify the meter asset state.
        
    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""
import sys
sys.path.insert(0, "..")
import math

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

    #test if the meter ID was informed as argument
    if len(sys.argv) != 2:
        print("Usage:",sys.argv[0],"<meter id>")
        exit(1)

    #get the meter ID
    meter_id = sys.argv[1]

    #format the name of the expected private key
    priv_key_file = meter_id + ".priv"

    #try to retrieve the private key
    try:
        priv_key = pickle.load(open(priv_key_file, "rb"))
    except:
        print("Private key not found. Encrypted measurement wont be decrypted.")
        priv_key = None

    #instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network.json")

    #get access to Fabric as Admin user
    admin = c_hlf.get_user('ptb.de', 'Admin')
    #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
    c_hlf.new_channel('ptb-channel')

    #creates a loop object to manage async transactions
    loop = asyncio.get_event_loop()

    #some feedback to the user
    print("Invoking getConsumption chaincode...")
    #Invoke the chaincode 'getConsumption'. The transaction retrieves the meter ID state from
    #the blockchain, which contains the encrypted accumulated consumption.
    response = loop.run_until_complete(
            c_hlf.chaincode_query(requestor=admin,channel_name='ptb-channel',
            peers=['peer0.ptb.de'],args=[meter_id],
            cc_name='fabmorph',cc_version=cc_version,fcn='getConsumption'
            ))
    #print all the asset content
    print(response)
    
    #response has the key/value asset struct in JSON format, so we use json library to load it
    data = json.loads(response)
    
    #tests if priv_key is valid
    if priv_key is not None:
        #get the encrypmeasure field and decrypt it
        decrypted = priv_key.raw_decrypt(int(data['encrypmeasure']))
                    
        #show message with the decrypted value
        print("Decrypt value:",decrypted)