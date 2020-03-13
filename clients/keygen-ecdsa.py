"""
    The BlockMeter Experiment
    ~~~~~~~~~
    This module generates a pair of elliptic curve keys that can 
    be used together the other modules. We use the curve NIST 256p.
    Also, we save the keys in the files <meter_id>.pub and 
    <meter_id>.priv.
        
    :copyright: © 2020 by Wilson Melo Jr.
"""
import sys
from ecdsa import SigningKey, NIST256p

if __name__ == "__main__":
    #test if the meter ID was informed as argument
    if len(sys.argv) != 2:
        print("Usage:",sys.argv[0],"<meter id>")
        exit(1)

    #get the meter ID
    meter_id = sys.argv[1]

    #feedback to the user
    print("Generating a key pair...")

    #instantiate a key pair, sk = private key, vk = public key
    sk = SigningKey.generate(curve=NIST256p)
    vk = sk.verifying_key

    #format the key names according to the meter ID
    pub_key_file = meter_id + ".pub"
    priv_key_file = meter_id + ".priv"

    #write keys in their respective files usando PEM format
    with open(priv_key_file, "wb") as f:
        f.write(sk.to_pem())
    with open(pub_key_file, "wb") as f:
        f.write(vk.to_pem())    

    #feedback is always good
    print("The keys were saved into",pub_key_file,"and",priv_key_file)
