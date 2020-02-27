"""
    The Paillier Experiment - Benchmark chaincode_invoke
    ~~~~~~~~~
    PLEASE DONT TRY TO EXECUTE THIS FILE, IT IS USELESS!
    This file is used only to keep a copy of a modified version of the
    chaincode_invoke(...) function implemented by the Fabric Python SDK.

    The original chaincode_invoke(...) implements the standard chaincode
    execution, which means:
        1) Sends the transaction to one or more endorser peers and wait;
        2) Check the endorsement envelop;
        3) Broadcasts the transaction (with the endorsement) to the orderer.

    Additionaly, the original chaincode_invoke(...) also waits for the transaction
    commit. If the commit does not happen before the timeout, it notifies the
    caller to submit the transaction again. This step is not part of the
    standard Fabric protocol. Apparently the Fabric Python SDK community decide
    to implement at this manner by trying to give to the caller a feedback about
    the chaincode execution success (or not).

    You will need the modify version of the chaincode_invoke(...) function to 
    run the client-morph-mp.py program in a proper manner. So you must do the 
    following:

        1) Find the file client.py in your Fabric Python SDK installation. In my
        machine, this file is in:
        /usr/local/lib/python3.6/dist-packages/hfc-0.7.0-py3.6.egg/hfc/fabric/client.py.

        2) Find the chaincode_invoke(...) function and replace its code by the code
        provided below.
    
    An important detail: We are working with the Fabric Python SDK version 0.7.0. If you
    are using a newer version, maybe it will be necessary to compare both codes a make
    some adaptations.

    :copyright: © 2019 by Wilson Melo Jr. (in behalf of PTB)    
"""
def chaincode_invoke(self, requestor, channel_name, peer_names, args,
                        cc_name, cc_version, cc_type=CC_TYPE_GOLANG,
                        fcn='invoke', timeout=10, mode=1):
    """
    Invoke chaincode for ledger update

    :param requestor: User role who issue the request
    :param channel_name: the name of the channel to send tx proposal
    :param peer_names: Names of the peers to install
    :param args (list): arguments (keys and values) for initialization
    :param cc_name: chaincode name
    :param cc_version: chaincode version
    :param cc_type: chaincode type language
    :param fcn: chaincode function
    :param timeout: timeout to wait
    :param mode: chooses between 3 modes of operation:
        1. Default mode, exactly as implemented by the Py-SDK Community
        2. Endorser benchmark - we stop the transaction after get the endorsement,
            i.e. we do not broadcast it to the orderer.
        3. Complete benchmark - we broadcast the transaction to the orderer, but
            we do not wait for its confirmation like in the default mode.
    :return: True or False
    """
    peers = []
    for peer_name in peer_names:
        peer = self.get_peer(peer_name)
        peers.append(peer)

    tran_prop_req = create_tx_prop_req(
        prop_type=CC_INVOKE,
        cc_name=cc_name,
        cc_version=cc_version,
        cc_type=cc_type,
        fcn=fcn,
        args=args
    )

    tx_context = create_tx_context(
        requestor,
        ecies(),
        tran_prop_req
    )

    res = self.get_channel(
        channel_name).send_tx_proposal(tx_context, peers)

    tran_req = utils.build_tx_req(res)

    tx_context_tx = create_tx_context(
        requestor,
        ecies(),
        tran_req
    )

    #test the invoke mode
    if mode == 2:
        #endorser benchmark is done, we stop here
        return res != None

    responses = utils.send_transaction(
        self.orderers, tran_req, tx_context_tx)

    res = tran_req.responses[0].response
    if not (res.status == 200 and responses[0].status == 200):
        return res.message

    #test the invoke mode
    if mode == 3:
        #the complete benchmark is done, we stop here
        return res != None

    # Wait until chaincode invoke is really effective
    # Note : we will remove this part when we have channel event hub
    starttime = int(time.time())
    payload = None
    while int(time.time()) - starttime < timeout:
        try:
            response = self.query_transaction(
                requestor=requestor,
                channel_name=channel_name,
                peer_names=peer_names,
                tx_id=tx_context.tx_id,
                decode=False
            )

            if response.response.status == 200:
                payload = tran_req.responses[0].response.payload
                return payload.decode('utf-8')

            time.sleep(1)
        except Exception:
            time.sleep(1)

    msg = 'Failed to invoke chaincode. Query check returned: %s'
    return msg % payload.message