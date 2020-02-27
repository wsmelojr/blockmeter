import sys
sys.path.insert(0, "..")

import time
import array as arr
from opcua import Client as client_opcua
from hfc.fabric import Client as client_fabric


if __name__ == "__main__":

    #instantiate the opcua client
    c_opcua = client_opcua("opc.tcp://localhost:4840/freeopcua/server/")

    #instantiate the hyperledeger fabric client
    c_hlf = client_fabric(net_profile="ptb-network.json")

    try:
        #connect to the opcua server
        c_opcua.connect()
        #opcua client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
        root = c_opcua.get_root_node()
        #print shows what is happening
        print("OPC-UA Objects node is: ", root)

        #get access to fabric as Admin user
        admin = c_hlf.get_user('ptb.de', 'Admin')
        #the HLF Python SDK do not read the channel configuration, we need to add it mannually
        c_hlf.new_channel('ptb-channel')

        #creates string to accumulate samples
        measures = ''
        #creates an iterator to control the number of samples in measures
        i = 0

        while True:
            #waits a little (we define our sampling rate)
            time.sleep(1)
            #gets the measurement sample from opcua server
            sample = root.get_child(["0:Objects", "2:MyObject", "2:System Load"])
            
            #print shows what is happening
            print("Sampled measurement:", sample.get_value())

            #decides if it is necessary a comma or not in the string concatenation
            if measures == '':
                #no comma
                comma = ''
            else:
                #put comma, please
                comma = ','

            #inserts the individual measurement into a list of samples
            measures = measures + comma + str(int(sample.get_value() * 10))
            i = i + 1

            #each 10 samples, sends a transaction to the blockchain, invoking a LR chaincode
            if i == 10:
                #print shows what is happening
                print("Formated string of samples: ", measures)

                #invoke the LR chaincode... 
                print("Invoking chaincode... ")
                
                #the chaincode calls 'insertMeasurement'. The transaction uses a key 'ptb' for
                #inserting the new measurement. User admin is used. 
                response = c_hlf.chaincode_invoke(requestor=admin,channel_name='ptb-channel',
                            peer_names=['peer0.ptb.de'],args=['ptb',measures],
                            cc_name='fabspeed',cc_version='1.0',fcn='insertMeasurement'
                            )

                #so far, so good
                print("Insertion OK, getting next measurement.")

                #flush the old samples, a new measurement will come
                measures = ''
                #resets the iterator of samples
                i = 0

    finally:
        #only opcua client must be disconnected
        c_opcua.disconnect()
