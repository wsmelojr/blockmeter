"""
    The Paillier Experiment - OPCUA Server
    ~~~~~~~~~
    This module implements an OPCUA Server. The code was get from
    other projects from PTB and simply used as it was.
    Some code lines were comment since they were not necessary to 
    the Paillier experiment.
"""

import sys
import psutil

sys.path.insert(0, "..")
import time

from opcua import ua, Server
from opcua.server.history_sql import HistorySQLite

if __name__ == "__main__":

    # setup our server
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    server.set_server_name("PTB Metrology Cloud Measuring Device")

    # setup our own namespace, not really necessary but should as spec
    uri = "http://examples.freeopcua.github.io"
    idx = server.register_namespace(uri)

    # get Objects node, this is where we should put our nodes
    objects = server.get_objects_node()

    # populating our address space
    myobj = objects.add_object(idx, "MyObject")
    myvar = myobj.add_variable(idx, "System Load", ua.Variant(psutil.cpu_percent(interval=1), ua.VariantType.Double))
    myvar.set_writable()  # Set MyVariable to be writable by clients

    # Configure server to use sqlite as history database (default is a simple memory dict)
    #server.iserver.history_manager.set_storage(HistorySQLite("device_history.sql"))

    # starting!
    server.start()

    # enable data change history for this particular node, must be called after start since it uses subscription
    server.historize_node_data_change(myvar, period=None, count=100)

    try:
        while True:
            time.sleep(1)
            myvar.set_value(psutil.cpu_percent(interval=1))
    finally:
        # close connection, remove subscriptions, etc
        server.stop()
