"""
    The BlockMeter Experiment
    ~~~~~~~~~
    This module is a modifying in the multithread client that enables multi processes.
    The advantage in using multi processes is that it enables a better using of
    the CPUs multicores. We can create a big load of simultaneous transactions,
    something that is absolutely necessary in performance tests.


    The module must be executed only after the verify-ecdsa-regMeter-mp.py. Also, the informed
    parameter must be the same in both modules. Basically, the verify-ecdsa-regMeter-mp.py
    registers of all the meter IDs that will be used by the multiprocess client.
    We are generating random messages.

    One should notice that we change the business logic in the manner how we invoke the
    chaincode. Once we have too many concurrent threads, we need to reduce the probability
    of key collision. It happens when consecutive transactions try to change the status of
    the same digital asset. We try to avoid this problem by creating a range of 100
    different meter IDs for each thread. When the thread is started, it receives a
    meter_id base number and a free range of 100 consecutive numbers. So the thread can
    increment the meter_id base into this range, preventing consecutive transactions with
    the same key.

    :copyright: © 2020 by Wilson Melo Jr. (on behalf of PTB)
"""
import sys

sys.path.insert(0, "..")
import random

import asyncio
import base64
import hashlib
from ecdsa import SigningKey, NIST256p
from ecdsa.util import sigencode_der, sigdecode_der
import time
from hfc.fabric import Client as client_fabric

import threading
import multiprocessing as mp
import csv

maxrand = 99


class TransactionThread(threading.Thread):
    """We implement a class to encapsulate threads.
    The send_transaction() method does all the job.

    Atributes:
        meter_id (str): the identifier of the meter
        priv_key (str): the private key
        thread_id: the sequential thread_id, which depends on
            the number of threads you create.
        c_lock: a thread locker (a mutex) to deal with
            concurrency in some specific functions of the Fabric SDK
        c_event: a shared thread event object to notify the
            threads that they must stop.
    Methods:
        send_transaction(): implements the respective chaincode invoke.
    """

    def __init__(self, thread_id, priv_key, c_lock, c_event):
        threading.Thread.__init__(self)
        # computes an unique ID to the meter. The formula must be the same used in verify-ecdsa-regMeter-mp.py
        self.meter_id = str((mp.current_process()._identity[0] - 1) * 10000 + thread_id * 100)

        # make a simple attribution of the other parameters
        self.priv_key = priv_key
        self.c_lock = c_lock
        self._stopevent = c_event
        self.statistics = []

    def run(self):
        """This method deals with control procedures related to the thread.
        It calls the send_transaction() method, and after it saves any statistics
        related to the transaction spent time.
        """
        # use print to log everything you need
        print("Starting...: " + self.meter_id)

        # send transaction to the endorser and to the order
        self.send_transactions()

        # save statistics in a .CSV file
        filename = str(self.meter_id) + ".csv"
        with open(filename, 'w') as csvFile:
            writer = csv.writer(csvFile)
            # writes the statistic vector into the csv file
            self.c_lock.acquire(1)
            writer.writerows(self.statistics)
            self.c_lock.release()
        csvFile.close()

        print("Exiting...: " + self.meter_id)

    def send_transactions(self):
        """This method implements execution code. It basically collects
        messages generated randomly and adds these new messages
        in the ledger. On it transaction, it also collects start and end times,
        logging them in the statistics vector.

        Notice that the Fabric invoke chaincode performs a transcation in two steps.
        First, the transaction is sent to a endorser peer. This call blocks the client
        (i.e., the client waits by the endorser response until a default timeout).
        After, the client sends the endorsed transaction to the orderer service, but do not
        wait by a response anymore. All these steps are encapsulated by the Fabric SDK.
        """
        # creates a loop object to manage async transactions
        loop = asyncio.new_event_loop()
        # configures the event loop of the current thread
        asyncio.set_event_loop(loop)

        # The function that starts the Fabric SDK does not support concurrency,
        # so we need the locker to synchronize the multithread access.
        self.c_lock.acquire(1)

        # we also creates a control to try again just in case the access to the SDK fails
        stop = False
        while not stop:
            try:
                # instantiate the Fabric SDK client (ptb-network-tls.json is our network profile)
                c_hlf = client_fabric(net_profile="ptb-network-tls.json")
                stop = True
            except:
                stop = False
        # now we can release the locker...
        self.c_lock.release()

        # get access to Fabric as Admin user
        admin = c_hlf.get_user('ptb.de', 'Admin')
        # the Fabric Python SDK do not read the channel configuration, we need to add it manually
        c_hlf.new_channel('ptb-channel')

        # we will change the meter_id within an offset to reduce the probability of key collision
        id_offset = 0
        max_offset = 100

        # the thread runs until the main program requests its stop
        while not self._stopevent.isSet():
            try:
                # generates a random message value between 1 and 99
                message = str(random.randint(1, maxrand))
                # modify the meter_id value
                meter_id_temp = str(int(self.meter_id) + id_offset)

                # test if priv_key is valid
                if self.priv_key is None:

                    print("Invalid Private Key -- Meter ID: " + meter_id_temp + " Message: " + message)

                    # signs the message using the private key and converts it to base64 encoding
                    signature = priv_key.sign(message.encode(), hashfunc=hashlib.sha256, sigencode=sigencode_der)
                    b64sig = base64.b64encode(signature)

                    # giving the signature feedback
                    print("Continuing with the information...\nmessage:", message, "\nsignature:", b64sig)

                    # take time message to generate statistics
                    start = time.time()

                    # the transaction calls chaincode 'checkSignature'. It uses the meter ID and
                    # signs the message using the private key and converts it to base64 encoding.
                    # inserting the new message. Admin is used.
                    response = loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,
                                               channel_name='ptb-channel',
                                               peers=['peer0.ptb.de'],
                                               cc_name='fabpki',
                                               cc_version='1.0',
                                               fcn='checkSignature',
                                               args=[meter_id_temp, str(message), b64sig],
                                               cc_pattern=None
                                               ))
                    # the signature checking returned... (true or false)
                    print("The signature verification returned:\n", response)
                    # take time message to generate statistics
                    end = time.time()
                    # append statistics to the respective list
                    self.statistics.append([start, end])

                else:
                    print("Valid Private Key -- Meter ID: " + meter_id_temp + " Message: " + message)
                    # signs the message using the private key and converts it to base64 encoding
                    signature = priv_key.sign(message.encode(), hashfunc=hashlib.sha256, sigencode=sigencode_der)
                    b64sig = base64.b64encode(signature)

                    # giving the signature feedback
                    print("Continuing with the information...\nmessage:", message, "\nsignature:", b64sig)

                    # take time message to generate statistics
                    start = time.time()

                    # the transaction calls chaincode 'checkSignature'. It uses the meter ID and
                    # signs the message using the private key and converts it to base64 encoding.
                    # inserting the new message. Admin is used.
                    response = loop.run_until_complete(
                        c_hlf.chaincode_invoke(requestor=admin,
                                               channel_name='ptb-channel',
                                               peers=['peer0.ptb.de'],
                                               cc_name='fabpki',
                                               cc_version='1.0',
                                               fcn='checkSignature',
                                               args=[meter_id_temp, str(message), b64sig],
                                               cc_pattern=None
                                               ))
                    # the signature checking returned... (true or false)
                    print("The signature verification returned:\n", response)
                    # take time message to generate statistics
                    end = time.time()
                    # append statistics to the respective list
                    self.statistics.append([start, end])

                # increments id_offset, reseting it when it is equal or greater than max_offset
                id_offset = (id_offset + 1) % max_offset

                # each thread generates 1 tsp... so it is time to sleep a little :-)
                # if not id_offset % 5:
                time.sleep(1)

                # so far, so good
                print("Insertion OK, getting next message...")

            except:
                # exceptions probably occur when the transaction fails. In this case, we
                # need to adjust the id_offset, so the thread has high chances of continue
                # executing with the next meter ID.
                id_offset = (id_offset + 1) % max_offset

                # self.c_lock.release()
                print("We are having problems with the exceptions...")


def multiproc(mnt, priv_key, slp, lock):
    # creates a locker to synchronize the threads
    c_lock = lock
    c_event = threading.Event()

    # creates a vector to keep the threads reference and join all them later
    threads = []

    # loop to create all the required threads
    for x in range(mnt):
        # creates the x-th thread
        t = TransactionThread(x, priv_key, c_lock, c_event)
        # add the thread to the reference vector
        threads.append(t)
        # starts the thread
        t.start()

    # let the threads run for the next slp seconds...
    time.sleep(slp)

    # notify the threads that they need to stop
    c_event.set()

    # recall the join for all create threads
    for t in threads:
        t.join()


if __name__ == "__main__":
    """The main program starts here. You just need to set a meter_id and how many 
    threads you need. After starts the thread, the program waits for an ENTER key press.
    Do that to notify all the threads and join them, stopping the program in a correct manner.

    Notice that all the threads are created to modify the status of a same meter_id.
    We implemented the code in this manner to force the amount of computing related to
    the transaction validate. However, the code can be easily changed to deal with
    different meter IDs. That shall require less computing effort to validate
    the transactions, once they will be modifying different digital asset states.
    """

    # test if we have correct arguments
    if not (len(sys.argv) == 4):
        print("Usage:", sys.argv[0], "<nprocesses> <nthreads> [<priv_key>]")
        exit(1)

    # get the number of threads and processes
    nprocesses = int(sys.argv[1])
    nthreads = int(sys.argv[2])

    # treats the private key (if it was provided)
    if len(sys.argv) == 4:
        try:
            # try to retrieve the private key
            priv_key_file = sys.argv[3]
            print(priv_key_file)
            with open(priv_key_file, 'r') as file:
                priv_key = SigningKey.from_pem(file.read())

        except:
            print("Invalid private key.", sys.argv[3])
            exit
    else:
        print("The private key is invalid!")
        priv_key = None

    # randomize our entropy source...
    random.seed(123)

    # if necessary, use this line to stop the multiprocessing execution until the user confirms
    input('Ready to create the multiprocesses. Press ENTER to start...\n')

    # setup a list of processes that we want to run
    processes = [mp.Process(target=multiproc,
                            args=(nthreads, priv_key, 120, threading.Lock()))
                 for x in range(nprocesses)]

    # run processes
    for p in processes:
        p.start()

    # exit the completed processes
    for p in processes:
        p.join()

