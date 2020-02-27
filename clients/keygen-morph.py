"""
    The Paillier Experiment - Keygen
    ~~~~~~~~~
    This module generates a pair of Paillier keys that can be used
    together the other modules. The keys are saved as serialized 
    objects, in the files <meter_id>.pub and <meter_id>.priv.
        
    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""
import sys
sys.path.insert(0, "..")
import math
import phe.encoding
from phe import paillier
import pickle

if __name__ == "__main__":
    #test if the meter ID was informed as argument
    if len(sys.argv) != 3:
        print("Usage:",sys.argv[0],"<meter id> <keysize>")
        exit(1)

    #get the meter ID
    meter_id = sys.argv[1]
    keysize = sys.argv[2]

    #feedback to the user
    print("Generating a key pair...")

    #instantiate a key pair for the Paillier Crypto 
    pub_key, priv_key = paillier.generate_paillier_keypair(None,int(keysize))

    #format the key names according to the meter ID
    pub_key_file = meter_id + ".pub"
    priv_key_file = meter_id + ".priv"

    #write keys in their respective files
    pickle.dump(pub_key,open(pub_key_file, "wb"))
    pickle.dump(priv_key,open(priv_key_file, "wb"))

    #feedback is always good
    print("The keys were saved into",pub_key_file,"and",priv_key_file)
