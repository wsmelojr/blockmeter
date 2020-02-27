/////////////////////////////////////////////
//    THE BLOCKCHAIN PKI EXPERIMENT     ////
///////////////////////////////////////////
/*
	This is the fabpki, a chaincode that implements a Public Key Infrastructure (PKI)
	for measuring instruments. It runs in Hyperledger Fabric 1.4.
	He was created as part of the PKI Experiment. You can invoke its methods
	to store measuring instruments public keys in the ledger, and also to verify
	digital signatures that are supposed to come from these instruments.

	@author: Wilson S. Melo Jr.
	@date: Oct/2019
*/
package main

import (
	//the majority of the imports are trivial...
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"strconv"
	"time"

	//these imports are for Hyperledger Fabric interface
	"github.com/hyperledger/fabric/core/chaincode/shim"
	sc "github.com/hyperledger/fabric/protos/peer"
)

/* All the following functions are used to implement fabpki chaincode. This chaincode
basically works with 2 main features:
	1) A Register Authority RA (e.g., Inmetro) verifies a new measuring instrument (MI) and attests
	the correspondence between the MI's private key and public key. After doing this, the RA
	inserts the public key into the ledger, associating it with the respective instrument ID.

	2) Any client can ask for a digital signature ckeck. The client informs the MI ID, an
	information piece (usually a legally relevant register) and its supposed digital signature.
	The chaincode retrieves the MI public key and validates de digital signature.
*/

// SmartContract defines the chaincode base structure. All the methods are implemented to
// return a SmartContrac type.
type SmartContract struct {
}

// Meter constitutes our key|value struct (digital asset) and implements a single
// record to manage the
// meter public key and measures. All blockchain transactions operates with this type.
// IMPORTANT: all the field names must start with upper case
type Meter struct {
	PubKey ecdsa.PublicKey `json:"pubkey"`
}

// Init method is called when the fabpki is instantiated.
// Best practice is to have any Ledger initialization in separate function.
// Note that chaincode upgrade also calls this function to reset
// or to migrate data, so be careful to avoid a scenario where you
// inadvertently clobber your ledger's data!
func (s *SmartContract) Init(stub shim.ChaincodeStubInterface) sc.Response {
	return shim.Success(nil)
}

// Invoke function is called on each transaction invoking the chaincode. It
// follows a structure of switching calls, so each valid feature need to
// have a proper entry-point.
func (s *SmartContract) Invoke(stub shim.ChaincodeStubInterface) sc.Response {
	// extract the function name and args from the transaction proposal
	fn, args := stub.GetFunctionAndParameters()

	//implements a switch for each acceptable function
	if fn == "registerMeter" {
		//registers a new meter into the ledger
		return s.registerMeter(stub, args)

	} else if fn == "checkSignature" {
		//inserts a measurement which increases the meter consumption counter. The measurement
		return s.checkSignature(stub, args)

	} else if fn == "sleepTest" {
		//retrieves the accumulated consumption
		return s.sleepTest(stub, args)

	} else if fn == "countHistory" {
		//look for a specific fill up record and brings its changing history
		return s.countHistory(stub, args)

	} else if fn == "countLedger" {
		//look for a specific fill up record and brings its changing history
		return s.countLedger(stub)

	} else if fn == "queryLedger" {
		//execute a CouchDB query, args must include query expression
		return s.queryLedger(stub, args)
	}

	//function fn not implemented, notify error
	return shim.Error("Chaincode do not support this function")
}

/*
	SmartContract::registerMeter(...)
	Does the register of a new meter into the ledger.
	The meter is the base of the key|value structure.
	The key constitutes the meter ID.
	- args[0] - meter ID
	- args[1] - the public key associated with the meter
*/
func (s *SmartContract) registerMeter(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if !(len(args) == 2 || len(args) == 3) {
		return shim.Error("It was expected the parameters: <meter id> <public key> [encrypted inital consumption]")
	}

	//gets the parameters associated with the meter ID and the public key (in string format)
	meterid := args[0]
	strpubkey := args[1]

	fmt.Println("That must be your public key: (", strpubkey, ")")

	var myPubKey = ecdsa.PublicKey{}

	//creates the meter record
	var meter = Meter{PubKey: myPubKey}

	//encapsulates meter in a JSON structure
	meterAsBytes, _ := json.Marshal(meter)

	//registers meter in the ledger
	stub.PutState(meterid, meterAsBytes)

	//loging...
	fmt.Println("Registering meter: ", meter)

	//notify procedure success
	return shim.Success(nil)
}

/*
	This method implements the insertion of encrypted measurements in the blockchain.
	The encryptation must uses the same public key configured to the meter.
	Notice that the informed measurement will be added (accumulated) to the the previous
	encrypted measurement consumption information.
	The vector args[] must contain two parameters:
	- args[0] - meter ID
	- args[1] - the encrypted measurement, in a string representing a big int number.
*/
func (s *SmartContract) checkSignature(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 2 {
		return shim.Error("It was expected 2 parameter: <meter ID> <measurement>")
	}

	//gets the parameter associated with the meter ID and the incremental measurement
	//meterid := args[0]

	//notify procedure success
	return shim.Success(nil)
}

/*
	This method is a dummy test that makes the endorser "sleep" for some seconds.
	It is usefull to check either the sleeptime affects the performance of concurrent
	transactions.
	- args[0] - sleeptime (in seconds)
*/
func (s *SmartContract) sleepTest(stub shim.ChaincodeStubInterface, args []string) sc.Response {
	//validate args vector lenght
	if len(args) != 1 {
		return shim.Error("It was expected 1 parameter: <sleeptime>")
	}

	//gets the parameter associated with the meter ID and the incremental measurement
	sleeptime, err := strconv.Atoi(args[0])

	//test if we receive a valid meter ID
	if err != nil {
		return shim.Error("Error on retrieving sleep time")
	}

	//tests if sleeptime is a valid value
	if sleeptime > 0 {
		//stops during sleeptime seconds
		time.Sleep(time.Duration(sleeptime) * time.Second)
	}

	//return payload with bytes related to the meter state
	return shim.Success(nil)
}

/*
   This method brings the changing history of a specific meter asset. It can be useful to
   query all the changes that happened with a meter value.
   - args[0] - asset key (or meter ID)
*/
func (s *SmartContract) queryHistory(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 1 {
		return shim.Error("It was expected 1 parameter: <key>")
	}

	historyIer, err := stub.GetHistoryForKey(args[0])

	//verifies if the history exists
	if err != nil {
		//fmt.Println(errMsg)
		return shim.Error("Fail on getting ledger history")
	}

	// buffer is a JSON array containing records
	var buffer bytes.Buffer
	var counter = 0
	buffer.WriteString("[")
	bArrayMemberAlreadyWritten := false
	for historyIer.HasNext() {
		//increments iterator
		queryResponse, err := historyIer.Next()
		if err != nil {
			return shim.Error(err.Error())
		}
		// Add a comma before array members, suppress it for the first array member
		if bArrayMemberAlreadyWritten == true {
			buffer.WriteString(",")
		}

		//generates a formated result
		buffer.WriteString("{\"Value\":")
		buffer.WriteString("\"")
		// Record is a JSON object, so we write as-is
		buffer.WriteString(string(queryResponse.Value))
		buffer.WriteString("\"")
		buffer.WriteString(", \"Counter\":")
		buffer.WriteString(strconv.Itoa(counter))
		//buffer.WriteString(queryResponse.Timestamp)
		buffer.WriteString("}")
		bArrayMemberAlreadyWritten = true

		//increases counter
		counter++
	}
	buffer.WriteString("]")
	historyIer.Close()

	//loging...
	fmt.Printf("Consulting ledger history, found %d\n records", counter)

	//notify procedure success
	return shim.Success(buffer.Bytes())
}

/*
   This method brings the number of times that a meter asset was modified in the ledger.
   It performs faster than queryHistory() method once it does not retrive any information,
   it only counts the changes.
   - args[0] - asset key (or meter ID)
*/
func (s *SmartContract) countHistory(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 1 {
		return shim.Error("It was expected 1 parameter: <key>")
	}

	historyIer, err := stub.GetHistoryForKey(args[0])

	//verifies if the history exists
	if err != nil {
		//fmt.Println(errMsg)
		return shim.Error("Fail on getting ledger history")
	}

	//creates a counter
	var counter int64
	counter = 0

	for historyIer.HasNext() {
		//increments iterator
		_, err := historyIer.Next()
		if err != nil {
			return shim.Error(err.Error())
		}

		//increases counter
		counter++

		fmt.Printf("Consulting ledger history, found %d\n records", counter)
	}
	// buffer is a JSON array containing records
	var buffer bytes.Buffer
	buffer.WriteString("[")
	buffer.WriteString("\"Counter\":")
	buffer.WriteString(strconv.FormatInt(counter, 10))
	buffer.WriteString("]")

	historyIer.Close()

	//loging...
	fmt.Printf("Consulting ledger history, found %d\n records", counter)

	//notify procedure success
	return shim.Success(buffer.Bytes())
}

/*
   This method counts the total of well succeeded transactions in the ledger.
*/
func (s *SmartContract) countLedger(stub shim.ChaincodeStubInterface) sc.Response {

	//use a range of keys, assuming that the max key value is 999999,
	resultsIterator, err := stub.GetStateByRange("0", "999999")
	if err != nil {
		return shim.Error(err.Error())
	}

	//defer iterator closes at the end of the function
	defer resultsIterator.Close()

	//creates a counter
	var counter int64
	var keys int64
	counter = 0
	keys = 0

	//the interator checks all the valid keys
	for resultsIterator.HasNext() {

		//increments iterator
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return shim.Error(err.Error())
		}

		//busca historico da proxima key
		historyIer, err := stub.GetHistoryForKey(queryResponse.Key)

		//verifies if the history exists
		if err != nil {
			//fmt.Println(errMsg)
			return shim.Error(err.Error())
		}

		defer historyIer.Close()

		for historyIer.HasNext() {
			//increments iterator
			_, err := historyIer.Next()
			if err != nil {
				return shim.Error(err.Error())
			}

			//increases counter
			counter++
		}
		fmt.Printf("Consulting ledger history, found key %s\n", queryResponse.Key)

		keys++
	}
	// buffer is a JSON array containing records
	var buffer bytes.Buffer
	buffer.WriteString("[")
	buffer.WriteString("\"Counter\":")
	buffer.WriteString(strconv.FormatInt(counter, 10))
	buffer.WriteString("\"Keys\":")
	buffer.WriteString(strconv.FormatInt(keys, 10))
	buffer.WriteString("]")

	//loging...
	fmt.Printf("Consulting ledger history, found %d transactions in %d keys\n", counter, keys)

	//notify procedure success
	return shim.Success(buffer.Bytes())
}

/*
   This method executes a free query on the ledger, returning a vector of meter assets.
   The query string must be a query expression supported by CouchDB servers.
   - args[0] - query string.
*/
func (s *SmartContract) queryLedger(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 1 {
		return shim.Error("It was expected 1 parameter: <query string>")
	}

	//using auxiliar variable
	queryString := args[0]

	//loging...
	fmt.Printf("Executing the following query: %s\n", queryString)

	//try to execute query and obtain records iterator
	resultsIterator, err := stub.GetQueryResult(queryString)
	//test if iterator is valid
	if err != nil {
		return shim.Error(err.Error())
	}
	//defer iterator closes at the end of the function
	defer resultsIterator.Close()

	// buffer is a JSON array containing QueryRecords
	var buffer bytes.Buffer
	buffer.WriteString("[")
	bArrayMemberAlreadyWritten := false
	for resultsIterator.HasNext() {
		//increments iterator
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return shim.Error(err.Error())
		}
		// Add a comma before array members, suppress it for the first array member
		if bArrayMemberAlreadyWritten == true {
			buffer.WriteString(",")
		}

		//generates a formated result
		buffer.WriteString("{\"Key\":")
		buffer.WriteString("\"")
		buffer.WriteString(queryResponse.Key)
		buffer.WriteString("\"")
		buffer.WriteString(", \"Record\":")
		// Record is a JSON object, so we write as-is
		buffer.WriteString(string(queryResponse.Value))
		buffer.WriteString("}")
		bArrayMemberAlreadyWritten = true
	}
	buffer.WriteString("]")

	//loging...
	fmt.Printf("Obtained the following fill up records: %s\n", buffer.String())

	//notify procedure success
	return shim.Success(buffer.Bytes())
}

/*
 * The main function starts up the chaincode in the container during instantiate
 */
func main() {

	////////////////////////////////////////////////////////
	// USE THIS BLOCK TO COMPILE THE CHAINCODE
	//if err := shim.Start(new(SmartContract)); err != nil {
	//	fmt.Printf("Error starting SmartContract chaincode: %s\n", err)
	//}
	////////////////////////////////////////////////////////

	////////////////////////////////////////////////////////
	// USE THIS BLOCK TO PERFORM ANY TEST WITH THE CHAINCODE

	//create pair of keys
	privateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		panic(err)
	}

	//marshal the keys in a buffer
	e, err := json.Marshal(privateKey)
	if err != nil {
		fmt.Println(err)
		return
	}

	_ = ioutil.WriteFile("ecdsa-keys.json", e, 0644)

	//read the saved key
	file, _ := ioutil.ReadFile("ecdsa-keys.json")

	myPrivKey := ecdsa.PrivateKey{}
	//myPubKey := ecdsa.PublicKey{}

	_ = json.Unmarshal([]byte(file), &myPrivKey)

	fmt.Println(myPrivKey)
	myPubKey := myPrivKey.PublicKey

	//test digital signature verifying
	msg := "hello, world"
	hash := sha256.Sum256([]byte(msg))

	r, s, err := ecdsa.Sign(rand.Reader, privateKey, hash[:])
	if err != nil {
		panic(err)
	}
	fmt.Printf("signature: (0x%x, 0x%x)\n", r, s)

	myPubKey.Curve = elliptic.P256()
	fmt.Println(myPubKey)

	valid := ecdsa.Verify(&myPubKey, hash[:], r, s)
	fmt.Println("signature verified:", valid)

	////////////////////////////////////////////////////////

}
