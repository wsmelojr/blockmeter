"""
    The BlockMeter Experiment
    ~~~~~~~~~
    This module generates a pair of elliptic curve keys that can 
    be used together the other modules. We save and serialize the keys
    in the files <meter_id>.pub and <meter_id>.priv.
        
    :copyright: © 2020 by Wilson Melo Jr.
"""
import sys
sys.path.insert(0, "..")
import math
import pickle
import base64
import hashlib
from ecdsa import SigningKey, NIST256p
from ecdsa.util import sigencode_der, sigdecode_der

if __name__ == "__main__":
    #test if the meter ID was informed as argument
    if len(sys.argv) != 2:
        print("Usage:",sys.argv[0],"<meter id>")
        exit(1)

    #get the meter ID
    meter_id = sys.argv[1]

    #feedback to the user
    print("Generating a key pair...")

    #instantiate a key pair
    sk = SigningKey.generate(curve=NIST256p)
    vk = sk.verifying_key

    vk_pem = vk.to_pem()
    vk_string = vk.to_string()
    print("Minha chave publica: ",vk_pem)

    #vk.precompute()
    signature = sk.sign(b"message", hashfunc=hashlib.sha256, sigencode=sigencode_der)
    b64sig = base64.b64encode(signature)
    print("Minha assinatura ANS.1: ", b64sig)


    #format the key names according to the meter ID
    pub_key_file = meter_id + ".pub"
    priv_key_file = meter_id + ".priv"

    #write keys in their respective files
    pickle.dump(vk,open(pub_key_file, "wb"))
    #pickle.dump(priv_key,open(priv_key_file, "wb"))

    #feedback is always good
    print("The keys were saved into",pub_key_file,"and",priv_key_file)
