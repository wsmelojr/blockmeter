"""
    The Paillier Experiment - Multithread Client
    ~~~~~~~~~
    This module implements a multithread client that produces
    a load of transactions against a Fabric endorser peer.
    You can use it to execute the following test cases:
        1) Endorser performance test with different Paillier
        key sizes;
        2) Endorser performance test comparing the same chaincode
        business rules using plaintext measurements OR homomorphic
        computing.        
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
import threading
import csv

#defines the chaincode version
cc_version = "1.0"

class TransactionThread(threading.Thread):
    """We implement a class to encapsulate threads.
    The send_transaction() method does all the job.

    Atributes:
        meter_id (str): the identifier of the meter
        pub_key (str): the Paillier public key
        thread_id: the sequencial thread_id, which dependes on
            the number of threads you create.
        c_lock: a thread locker (a mutex) to deal with 
            concurrency in some specific functions of the Fabric SDK
        c_event: a shared thread event object to notify the
            threads that they must stop. 
    Methods:
        send_transaction(): treats the OPCUA communication and implements
        the respective chaincode invoke.
    """
    def __init__(self, meter_id, pub_key, thread_id, c_lock, c_event):
        threading.Thread.__init__(self)
        self.meter_id = meter_id
        self.pub_key = pub_key
        self.id = thread_id
        self.c_lock = c_lock
        self._stopevent = c_event
        self.statistics = []

    def run(self):
        """This method deals with control procedures related to the thread.
        It calls the send_transaction() method, and after it saves any statistics
        related to the transaction spent time.
        """
        #use print to log everything you need
        print("Starting...: " + str(self.id))

        #send transaction to the endorser and to the order
        self.send_transactions()

        #save statistics in a .CSV file
        filename = str(self.id) + ".csv"
        with open(filename, 'w') as csvFile:
            writer = csv.writer(csvFile)
            #writes the statistic vector into the csv file
            writer.writerows(self.statistics)
        csvFile.close()

        print("Exiting...: " + str(self.id))

    def send_transactions(self):
        """This method implements the thread execution code. It basically collects 
        measurements from a UPCUA server and adds these new measurements to the 
        consumption value in the ledger. If the meter_id has a pair of Paillier keys,
        it sends a encrypted measurement by invoking insertMeasurement chaincode. 
        Otherwise, it sends a plaintext measurement by invoking insertPlaintextMeasurement
        chaincode. On it transaction, it collects start and end times, logging them in the
        statistics vector.

        Notice that the Fabric chaincode invoke performs a transcation in two steps.
        First, the transaction is sent to a endorser peer. That call blocks the client
        (i.e., the client waits by the endorser response until the default timeout).
        After, the client sends the endorsed transaction to the orderer service, but do not
        wait by a response anymore. All these steps are encapsulated by the Fabric SDK.
        """
        #The function that starts the Fabric SDK does not support concurrency,
        # so we need the locker to synchronize the multithread access.
        c_lock.acquire(1)

        #instantiate the Fabric SDK client (ptb-network.json is our network profile)
        c_hlf = client_fabric(net_profile="ptb-network.json")
        
        #now we can release the locker...
        c_lock.release()

        #instantiate the opcua client
        c_opcua = client_opcua("opc.tcp://localhost:4840/freeopcua/server/")

        try:
            #get access to Fabric as Admin user
            admin = c_hlf.get_user('ptb.de', 'Admin')
            #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
            c_hlf.new_channel('ptb-channel')

            #creates a loop object to manage async transactions
            loop = asyncio.get_event_loop()

            #connect to the opcua server
            c_opcua.connect()
            #opcua client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
            root = c_opcua.get_root_node()
            #print shows what is happening
            #print("OPC-UA Objects node is: ", root)

            while not self._stopevent.isSet():
                #waits a little (we define our sampling rate)
                #time.sleep(5)
                #gets the measurement sample from opcua server
                sample = root.get_child(["0:Objects", "2:MyObject", "2:System Load"])
                
                #print shows what is happening
                #print("Sampled measurement: ", sample.get_value())

                #inserts the individual measurement into var param
                measurement = int(sample.get_value() * 10)

                #test if pub_key is valid
                if pub_key is None:
                    #invoke the LR chaincode... 
                    print("insertPlainTextMeasurement:(t=" + str(self.id) + ",m=" + str(measurement) + ")") 
                    
                    #take time measurement for generating statistics
                    start = time.time()

                    #the transaction calls chaincode 'insertPlainTextMeasurement'. It uses the meter ID for
                    #inserting the new measurement. Admin is used. 
                    response = loop.run_until_complete(
                                c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                                peers=['peer0.ptb.de'],args=[meter_id,str(measurement)],
                                cc_name='fabmorph',cc_version=cc_version,fcn='insertPlainTextMeasurement'
                                ))

                    #take time measurement for generating statistics
                    end = time.time()
                    #append statistics to the respective list
                    self.statistics.append([start,end])
                else:
                    #encrypts measurement using pub_key
                    encrypted = str(pub_key.raw_encrypt(measurement))

                    #invoke the LR chaincode... 
                    print("insertMeasurement:(t=" + str(self.id) + ",m=" + encrypted + ")") 

                    #take time measurement for generating statistics
                    start = time.time()

                    #the transaction calls chaincode 'insertMeasurement'. It uses the meter ID for
                    #inserting the new measurement. Admin is used. 
                    response = loop.run_until_complete(
                                c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                                peers=['peer0.ptb.de'],args=[meter_id,encrypted],
                                cc_name='fabmorph',cc_version=cc_version,fcn='insertMeasurement'
                                ))

                    #take time measurement for generating statistics
                    end = time.time()
                    #append statistics to the respective list
                    self.statistics.append([start,end])
                
                #let's see what we did get...
                print(response)

                #so far, so good
                #print("Insertion OK, getting next measurement...")

        finally:
            #only opcua client need to be disconnected
            c_opcua.disconnect()

if __name__ == "__main__":
    """The main program starts here. You just need to set a meter_id and how many 
    threads you need. After starts the thread, the program waits for an ENTER key press.
    Do that to notify all the threads and join them, stoping the program in a correct manner.

    Notice that all the threads are created to modify the status of a same meter_id.
    We implemented the code in this manner to force the amount of computing related to
    the transaction validate. However, the code can be easily changed to deal with
    different meter IDs. That shall require less computing effort to validate
    the transactions, once they will be modifying different digital asset states.
    """
    #test if the meter ID was informed as argument
    if len(sys.argv) != 3:
        print("Usage:",sys.argv[0],"<meter id> <nthreads>")
        exit(1)

    #get the meter ID and the number of threads you need
    meter_id = sys.argv[1]
    nthreads = int(sys.argv[2])

    #format the name of the expected public key
    pub_key_file = meter_id + ".pub"

    #try to retrieve the public key
    try:
        pub_key = pickle.load(open(pub_key_file, "rb"))
    except:
        print("Without a public key. We will continue as a plaintext.")
        pub_key = None       

    #creates a locker to synchronize the threads
    c_lock = threading.Lock()
    c_event = threading.Event()

    #creates a vector to keep the threads reference and join all them later
    threads = []

    #loop to create all the required threads
    for x in range(nthreads):
        #creates the x-th thread
        t = TransactionThread(meter_id,pub_key,x,c_lock,c_event)
        #add the thread to the reference vector
        threads.append(t)
        #starts the thread
        t.start()

    #generates a input requesting which in practice waits for the ENTER to stop the threads
    input('Press ENTER to stop the threads...\n')

    #notify the threads that they need to stop
    c_event.set()

    #recall the join for all create threads
    for t in threads:
        t.join()
