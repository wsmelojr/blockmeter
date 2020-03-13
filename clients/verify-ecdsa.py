"""
    The BlockMeter Experiment
    ~~~~~~~~~
    This module is necessary to register a meter in the blockchain. It
    receives the meter ID and its respective public key.
    This module must be called before any query against the ledger.
        
    :copyright: © 2020 by Wilson Melo Jr.
"""

import sys
from hfc.fabric import Client as client_fabric
import asyncio
import base64
import hashlib
from ecdsa import SigningKey, NIST256p
from ecdsa.util import sigencode_der, sigdecode_der

if __name__ == "__main__":

    #test if the meter ID was informed as argument
    if len(sys.argv) != 3:
        print("Usage:",sys.argv[0],"<meter id> <message>")
        exit(1)

    #get the meter ID
    meter_id = sys.argv[1]
    message = sys.argv[2]

    #format the name of the expected private key
    priv_key_file = meter_id + ".priv"

    #try to retrieve the private key
    try:
        print(priv_key_file)
        with open(priv_key_file, 'r') as file:
            priv_key = SigningKey.from_pem(file.read())
    except:
        print("I could not find a valid private key to the meter",meter_id)
        exit(1)

    #signs the message using the private key and converts it to base64 encoding
    signature = priv_key.sign(message.encode(), hashfunc=hashlib.sha256, sigencode=sigencode_der)
    b64sig = base64.b64encode(signature)

    #giving the signature feedback
    print("Continuing with the information...\nmessage:", message, "\nsignature:", b64sig)

    #creates a loop object to manage async transactions
    loop = asyncio.get_event_loop()

    #instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network-tls.json")

    #get access to Fabric as Admin user
    admin = c_hlf.get_user('ptb.de', 'Admin')
    
    #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
    c_hlf.new_channel('ptb-channel')

    #invoke the chaincode to register the meter
    response = loop.run_until_complete(c_hlf.chaincode_invoke(
        requestor=admin, 
        channel_name='ptb-channel', 
        peers=['peer0.ptb.de'],
        cc_name='fabpki', 
        cc_version='1.1',
        fcn='checkSignature', 
        args=[meter_id, message, b64sig], 
        cc_pattern=None))

    #the signature checking returned... (true or false)
    print("The signature verification returned:\n", response)