"""
    The BlockMeter Experiment
    ~~~~~~~~~
    This module is part of the multiprocessing client test. It prepare the test
    by registering 100 unique meter IDs for each individual thread. For instance,
    run the benchmark with 10 processes and 10 threads, this bechmark will create
    10*10*100 = 10000 unique IDs. We need to prevent our concurrent
    transactions creates key collision (to learn more about this, we recommend the
    following text:
    https://medium.com/@gatakka/how-to-prevent-key-collisions-in-hyperledger-fabric-chaincode-303700716733).

    :copyright: © 2020 by Wilson Melo Jr. (on behalf of PTB)
"""

import sys

sys.path.insert(0, "..")
from hfc.fabric import Client as client_fabric
import asyncio

if __name__ == "__main__":

    # test if the meter ID was informed as argument
    if len(sys.argv) != 4:
        print("Usage:", sys.argv[0], "<meter id> <nprocesses> <nthreads>")
        exit(1)

    # get the meter ID
    meter_id = sys.argv[1]
    # get the number of threads and process
    nprocesses = int(sys.argv[2])
    nthreads = int(sys.argv[3])

    # format the name of the expected public key
    pub_key_file = meter_id + ".pub"

    # try to retrieve the public key
    try:
        with open(pub_key_file, 'r') as file:
            pub_key = file.read()
    except:
        print("I could not find a valid public key to the meter", meter_id)
        exit(1)

    # shows the meter public key
    print("Continuing with the public key:\n", pub_key)

    # creates a loop object to manage async transactions
    loop = asyncio.get_event_loop()

    # instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network-tls.json")

    # get access to Fabric as Admin user
    admin = c_hlf.get_user('ptb.de', 'Admin')

    # the Fabric Python SDK do not read the channel configuration, we need to add it mannually
    c_hlf.new_channel('ptb-channel')

    # query peer installed chaincodes, make sure the chaincode is installed
    print("Checking if the chaincode fabpki is properly installed:")
    response = loop.run_until_complete(c_hlf.query_installed_chaincodes(
        requestor=admin,
        peers=['peer0.ptb.de']
    ))
    print(response)

    # we will create 100 meter IDs for each thread. So we need to multiple the following
    # operation: nprocess * nthreads * 1000
    for i in range(nprocesses):
        for j in range(nthreads):
            for k in range(100):
                # creates an unique meter ID
                meter_id = str(i * 10000 + j * 100 + k)

                # show the progress...
                print("Inserting meter ID " + meter_id + "...")
                response = loop.run_until_complete(c_hlf.chaincode_invoke(
                    requestor=admin,
                    channel_name='ptb-channel',
                    peers=['peer0.ptb.de'],
                    cc_name='fabpki',
                    cc_version='1.0',
                    fcn='registerMeter',
                    args=[meter_id, pub_key],
                    cc_pattern=None))

    # so far, so good
    print("Success on register meter and public key!", response)
