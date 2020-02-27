"""
    The Paillier Experiment - Multiprocessing Client
    ~~~~~~~~~
    This module is a modifying in the multithread client that enables multi processes. 
    The advantage in using multi processes is that it enables a better using of 
    the CPUs multicores. We can create a big load of simultaneous transactions, 
    something that is absolutely necessary in performance tests. 

    Besides the change to deal with multi processes, we also removed OPC-UA 
    implementation, once the number of process easily exceeds the number of possible
    simultaneous sockets supported by the operating system. In replacement, we are
    generating random measurements.

    This module requires a modified version of the chaincode_invoke(...) function into
    the Fabric Python SDK. We described how to do that in the file benchmark.py. The
    new chaincode_invoke(...) can be used in three different modes, two of them 
    tailored to be used by this program.

    The module must be executed only after the prepare-morph-mp.py. Also, the informed 
    parameter must be the same in both modules. Basically, the prepare-morph-mp.py does
    the register of all the meter IDs that will be used by the multiprocess client.
    One should notice that we change the business logic in the manner how we invoke the 
    chaincode. Once we have too many concurrent threads, we need to reduce the probability
    of key collision. It happens when consecutive transactions try to change the status of
    the same digital asset. We try to avoid this problem by creating a range of 100
    different meter IDs for each thread. When the thread is started, it receives a 
    meter_id base number and a free range of 100 consecutive numbers. So the thread can
    increment the meter_id base into this range, preventing consecutive transactions with
    the same key.
    
    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""
import sys
sys.path.insert(0, "..")
import os
import signal
import math
import random

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
import multiprocessing as mp
import csv

#defines the chaincode version
cc_version = "1.0"
encrypted_values = []
maxrand = 99

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
    def __init__(self, thread_id, mode, pub_key, kbits, c_lock, c_event):
        threading.Thread.__init__(self)
        #computes an unique ID to the meter. The formula must be the same used in prepare-morph-mp.py
        self.meter_id = str((mp.current_process()._identity[0] -1) * 10000 + thread_id *100)

        #make a simple attribution of the other parameters
        self.mode = mode
        self.pub_key = pub_key
        self.kbits = kbits
        self.c_lock = c_lock
        self._stopevent = c_event
        self.statistics = []

    def run(self):
        """This method deals with control procedures related to the thread.
        It calls the send_transaction() method, and after it saves any statistics
        related to the transaction spent time.
        """
        #use print to log everything you need
        print("Starting...: " + self.meter_id)
        
        #send transaction to the endorser and to the order
        self.send_transactions()

        #save statistics in a .CSV file
        filename = str(self.meter_id) + ".csv"
        with open(filename, 'w') as csvFile:
            writer = csv.writer(csvFile)
            #writes the statistic vector into the csv file
            self.c_lock.acquire(1)
            writer.writerows(self.statistics)
            self.c_lock.release()
        csvFile.close()

        print("Exiting...: " + self.meter_id)

    def send_transactions(self):
        """This method implements the thralso ead execution code. It basically collects 
        measurements from a UPCUA server also and adds these new measurements to the 
        consumption value in the ledger. also If the meter_id has a pair of Paillier keys,
        it sends a encrypted measurement also by invoking insertMeasurement chaincode. 
        Otherwise, it sends a plaintext malso easurement by invoking insertPlaintextMeasurement
        chaincode. On it transaction, it also collects start and end times, logging them in the
        statistics vector.

        Notice that the Fabric invoke chaincode performs a transcation in two steps.
        First, the transaction is sent to a endorser peer. This call blocks the client
        (i.e., the client waits by the endorser response until a default timeout).
        After, the client sends the endorsed transaction to the orderer service, but do not
        wait by a response anymore. All these steps are encapsulated by the Fabric SDK.
        """
        #creates a loop object to manage async transactions
        loop = asyncio.new_event_loop()
        #configures the event loop of the current thread
        asyncio.set_event_loop(loop)

        #The function that starts the Fabric SDK does not support concurrency,
        # so we need the locker to synchronize the multithread access.
        self.c_lock.acquire(1)

        #we also creates a control to try again just in case the access to the SDK fails
        stop = False
        while not stop:
            try:
                #instantiate the Fabric SDK client (ptb-network.json is our network profile)
                c_hlf = client_fabric(net_profile="ptb-network.json")                
                stop = True
            except:
                stop = False        
        #now we can release the locker...
        self.c_lock.release()

        #get access to Fabric as Admin user
        admin = c_hlf.get_user('ptb.de', 'Admin')
        #the Fabric Python SDK do not read the channel configuration, we need to add it mannually
        c_hlf.new_channel('ptb-channel')

        #we will change the meter_id within an offset to reduce the probability of key collision
        id_offset = 0
        max_offset = 100

        encrypted = ""

        #the thread runs until the main program requests its stop
        while not self._stopevent.isSet():
            try:
                #generates a random measurement value between 1 and 99
                measurement = random.randint(1,maxrand)

                #modify the meter_id value
                meter_id_temp = str(int(self.meter_id) + id_offset)

                #test if pub_key is valid
                if self.pub_key is None:
                    #invoke the LR chaincode... 
                    print("insertPlainTextMeasurement:(t=" + meter_id_temp + ",m=" + str(measurement) + ")")
                    
                    #take time measurement to generate statistics
                    start = time.time()

                    #the transaction calls chaincode 'insertPlainTextMeasurement'. It uses the meter ID for
                    #inserting the new measurement. Admin is used.
                    loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                        peers=['peer0.ptb.de'],args=[meter_id_temp,str(measurement)],
                        cc_name='fabmorph',cc_version=cc_version,fcn='insertPlainTextMeasurement'
                    ))
                    
                    #take time measurement to generate statistics
                    end = time.time()

                    #append statistics to the respective list
                    self.statistics.append([start,end])
                else:
                    #get previously encrypted value
                    encrypted = encrypted_values[measurement]

                    #invoke the LR chaincode... 
                    print("insertMeasurement:(t=" + meter_id_temp + ",m=" + encrypted + ")") 

                    #take time measurement to generate statistics
                    start = time.time()

                    #the transaction calls chaincode 'insertMeasurement'. It uses the meter ID for
                    #inserting the new measurement. Admin is used. 
                    loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                        peers=['peer0.ptb.de'],args=[meter_id_temp,encrypted],
                        cc_name='fabmorph',cc_version=cc_version,fcn='insertMeasurement'
                    ))
                    
                    #take time measurement to generate statistics
                    end = time.time()
                    #append statistics to the respective list
                    self.statistics.append([start,end])                    
                
                #increments id_offset, reseting it when it is equal or greater than max_offset
                id_offset = (id_offset + 1) % max_offset

                #each thread generates 1 tsp... so it is time to sleep a little :-)
                #if not id_offset % 5:
                time.sleep(1)

                #so far, so good
                #print("Insertion OK, getting next measurement...")

            except:
                #exceptions probably occur when the transaction fails. In this case, we
                #need to adjust the id_offset, so the thread has high chances of continue 
                #executing with the next meter ID.
                id_offset = (id_offset + 1) % max_offset

                #self.c_lock.release()
                print("We are having problems with the exceptions...")

def multiproc(mode, mnt, pub_key, kbits, slp, lock):
    #creates a locker to synchronize the threads
    c_lock = lock
    c_event = threading.Event()

    #creates a vector to keep the threads reference and join all them later
    threads = []

    #loop to create all the required threads
    for x in range(mnt):
        #creates the x-th thread
        t = TransactionThread(x, mode, pub_key, kbits, c_lock,c_event)
        #add the thread to the reference vector
        threads.append(t)
        #starts the thread
        t.start()

    #let the threads run for the next slp seconds...    
    time.sleep(slp)

    #notify the threads that they need to stop
    c_event.set()

    #recall the join for all create threads
    for t in threads:
        t.join()


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

    #test if we have correct arguments
    if not (len(sys.argv) == 4 or len(sys.argv) == 6):
        print("Usage:",sys.argv[0],"<mode> <nprocesses> <nthreads> [<pubkey> <kbits>]")
        exit(1)

    #get the number of threads and benchmark mode
    mode = int(sys.argv[1])
    nprocesses = int(sys.argv[2])
    nthreads = int(sys.argv[3])
    kbits = "0"

    #treats the public key (if it was provided)
    if len(sys.argv) == 6:     
        try:
            #try to retrieve the public key
            pub_key = pickle.load(open(sys.argv[4], "rb"))
            kbits = sys.argv[5]

            #since we are working with cryptography, we try to create a vector of 
            #previously encrypted values
            print("Creating vector of encrypted measurements...")
            for i in range(maxrand):
                encrypted_values.append(str(pub_key.raw_encrypt(i)))
        except:
            print("Invalid public key.",sys.argv[4])
            exit
    else:
        print("Without a public key. Measures will be considered as plaintext.")
        pub_key = None

    #randomize our entropy source...    
    random.seed(123)

    #if necessary, use this line to stop the multiprocessing execution until the user confirms
    #input('Ready to create the multiprocesses. Press ENTER to start...\n')
    
    #start subprocess to execute script which collects CPU statistics
    command = ['../blockchain/dockerstats.sh', 'dockerstats.sh', 'dev-peer0.ptb.de-fabmorph-1.0', 'peer0.ptb.de', 'couchdb0']
    stats_pid = os.spawnlp(os.P_NOWAIT, *command)

    #setup a list of processes that we want to run
    processes = [mp.Process(target=multiproc, 
                            args=(mode, nthreads, pub_key, kbits, 120, threading.Lock())) 
                            for x in range(nprocesses)]

    #run processes
    for p in processes:
        p.start()

    #exit the completed processes
    for p in processes:
        p.join()

    #kill the process which collect statistics in background
    os.kill(int(stats_pid), signal.SIGKILL)
