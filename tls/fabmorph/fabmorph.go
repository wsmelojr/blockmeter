package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"crypto/rand"
	"math/big"
	"errors"
	"io"
	"time"

	"github.com/hyperledger/fabric/core/chaincode/shim"
	sc "github.com/hyperledger/fabric/protos/peer"
)

////////////////////////////////////////
//////// GOMORPH INSERTION CODE ////////
////////////////////////////////////////

/* All the following functions belongs to the Gomorph Library. We insert all the code into the chaincode
main package because it was easier than make Hyperledger Fabric to accept external packages.
Gomorph is available at https://github.com/radicalrafi/gomorph.

	Paillier cryptosystem implementation

	Provides primitives for Public & Private Key Generation /  Encryption / Decryption
	Provides Functions to operate on the Cyphertext according to Paillier algorithm

	@author: radicalrafi
	@license: Apache 2.0

*/

/* The Paillier crypto system picks two keys p & q and denotes n = p*q
Messages have to be in the ring Z/nZ (integers modulo n)
Therefore a Message can't be bigger than n
*/
var ErrLongMessage = errors.New("Gaillier Error #1: Message is too long for The Public-Key Size \n Message should be smaller than Key size you choose")

//constants

var one = big.NewInt(1)

//Key structs

type PubKey struct {
	KeyLen int
	N      *big.Int //n = p*q (where p & q are two primes)
	G      *big.Int //g random integer in Z\*\n^2
	Nsq    *big.Int //N^2
}

type PrivKey struct {
	KeyLen int
	PubKey
	L *big.Int //lcm((p-1)*(q-1))
	U *big.Int //L^-1 modulo n mu = U = (L(g^L mod N^2)^-1)
}

func GenerateKeyPair(random io.Reader, bits int) (*PubKey, *PrivKey, error) {

	p, err := rand.Prime(random, bits/2)

	if err != nil {
		return nil, nil, err
	}

	q, err := rand.Prime(random, bits/2)

	if err != nil {
		return nil, nil, err
	}

	//N = p*q

	n := new(big.Int).Mul(p, q)

	nSq := new(big.Int).Mul(n, n)

	g := new(big.Int).Add(n, one)

	//p-1
	pMin := new(big.Int).Sub(p, one)
	//q-1
	qMin := new(big.Int).Sub(q, one)
	//(p-1)*(q-1)
	l := new(big.Int).Mul(pMin, qMin)
	//l^-1 mod n
	u := new(big.Int).ModInverse(l, n)
	pub := &PubKey{KeyLen: bits, N: n, Nsq: nSq, G: g}
	return pub, &PrivKey{PubKey: *pub, KeyLen: bits, L: l, U: u}, nil
}

/*
	Encrypt :function to encrypt the message into a paillier cipher text
	using the following rule :
	cipher = g^m * r^n mod n^2
	* r is random integer such as 0 <= r <= n
	* m is the message
*/
func Encrypt(pubkey *PubKey, message []byte) ([]byte, error) {

	r, err := rand.Prime(rand.Reader, pubkey.KeyLen)
	if err != nil {
		return nil, err
	}

	m := new(big.Int).SetBytes(message)
	if pubkey.N.Cmp(m) < 1 {
		return nil, ErrLongMessage
	}
	//c = g^m * r^nmod n^2

	//g^m
	gm := new(big.Int).Exp(pubkey.G, m, pubkey.Nsq)
	//r^n
	rn := new(big.Int).Exp(r, pubkey.N, pubkey.Nsq)
	//prod = g^m * r^n
	prod := new(big.Int).Mul(gm, rn)

	c := new(big.Int).Mod(prod, pubkey.Nsq)

	return c.Bytes(), nil
}

/*
	Decrypts a given ciphertext following the rule:
	m = L(c^lambda mod n^2).mu mod n
	* lambda : L
	* mu : U

*/
func Decrypt(privkey *PrivKey, cipher []byte) ([]byte, error) {

	c := new(big.Int).SetBytes(cipher)

	if privkey.Nsq.Cmp(c) < 1 {
		return nil, ErrLongMessage
	}

	//c^l mod n^2
	a := new(big.Int).Exp(c, privkey.L, privkey.Nsq)

	//L(x) = x-1 / n we compute L(a)
	l := new(big.Int).Div(new(big.Int).Sub(a, one), privkey.N)

	//computing m
	m := new(big.Int).Mod(new(big.Int).Mul(l, privkey.U), privkey.N)

	return m.Bytes(), nil

}

/*
	Homomorphic Properties of Paillier Cryptosystem

	* The product of two ciphers decrypts to the sum of the plain text
	* The product of a cipher with a non-cipher raising g will decrypt to their sum
	* A Cipher raised to a non-cipher decrypts to their product
	* Any cipher raised to an integer k will decrypt to the product of the deciphered and k
*/

//Add two ciphers together
func Add(pubkey *PubKey, c1, c2 []byte) []byte {

	a := new(big.Int).SetBytes(c1)
	b := new(big.Int).SetBytes(c2)

	// a * b mod n^²
	res := new(big.Int).Mod(new(big.Int).Mul(a, b), pubkey.Nsq)

	return res.Bytes()
}

//Add a constant & a cipher
func AddConstant(pubkey *PubKey, cipher, constant []byte) []byte {

	c := new(big.Int).SetBytes(cipher)
	k := new(big.Int).SetBytes(constant)

	//result = c * g^k mod n^2
	res := new(big.Int).Mod(
		new(big.Int).Mul(c, new(big.Int).Exp(pubkey.G, k, pubkey.Nsq)), pubkey.Nsq)

	return res.Bytes()

}

//Multiplication by a constant integer
func Mul(pubkey *PubKey, cipher, constant []byte) []byte {

	c := new(big.Int).SetBytes(cipher)
	k := new(big.Int).SetBytes(constant)

	//res = c^k mod n^2
	res := new(big.Int).Exp(c, k, pubkey.Nsq)

	return res.Bytes()
}

////////////////////////////////////////
//////// GOMORPH CODE ENDS HERE ////////
////////////////////////////////////////



//////////////////////////////////////
//////// FABMORPH - CHAINCODE ////////
//////////////////////////////////////

/* All the following functions are used to implemetn fabmorph chaincode. This chaincode
basically works with 2 scenarios:
	1) A measurement instrument sends measures in plain text to the blockchain. The smartcontract
	applies homomorphic cryptography and stores encrypted measures. The client can recover it by
	reading the encrypted value and decrypting locally.
	2) A measurement instrument sends encrypted measures. The smartcontract applies homomorphic 
	operations to obtain the (encrypted) total consumption value and to store it in the ledger.
	The client can it by reading the encrypted value and decrypting locally.

	@author: Wilson S. Melo Jr.
	@date: Apache 2.0

*/

/*
 * This is an auxiliar function to convert the Pallier public key struct into a string.
 * It is necessary to lead with the object in Fabric transactions.
 * The key in string format will have the 4 fields in the following order: KeyLen, N, G, Nsq 
 */
func PubKey2String(pubkey *PubKey) (string){
	return strconv.Itoa(pubkey.KeyLen) + "," + pubkey.N.String() + "," + pubkey.G.String() + "," + pubkey.Nsq.String()
}

/*
 * This is an auxiliar function to convert a string key into the Pallier public key struct.
 * It is necessary to lead with the object in Fabric transactions.
 * The key in string format MUST be formated with 4 comma-separate substrings, that correspond to the
 * respective fields: KeyLen, N, G, Nsq.
 * Example: 
 * "512,9317708529424897702020382930116702407110920461631622943398410342176567591986029379418525445868266
	642035599843718252107477949966673217711651921453503121487,9317708529424897702020382930116702407110920
	46163162294339841034217656759198602937941852544586826664203559984371825210747794996667321771165192145
	3503121488,868196922393174897253161831767710200925181500218099202121385823388772389324857444497325510
	95045029334111747236626667783012791667259632343428969631355566392144138916566553732073336450909522598
	17833785123113998363351341374266805275045098714823061322751114829098157258427086799436922320373510493
	4252452681091169"
 * which means:
	KeyLen = 512
	N = 9317708529424897702020382930116702407110920461631622943398410342176567591986029379418525445868266
	642035599843718252107477949966673217711651921453503121487
	G = 9317708529424897702020382930116702407110920461631622943398410342176567591986029379418525445868266
	642035599843718252107477949966673217711651921453503121488
	Nsq = 86819692239317489725316183176771020092518150021809920212138582338877238932485744449732551095045
	02933411174723662666778301279166725963234342896963135556639214413891656655373207333645090952259817833
	78512311399836335134137426680527504509871482306132275111482909815725842708679943692232037351049342524
	52681091169
 */
func String2PubKey(pubkey string) (*PubKey){
	//extract tokens from pubkey string to a vector
	strvec := strings.Split(pubkey, ",")

	if len(strvec) != 4 {
		return nil
	}

	//get the key lenght
	l, err := strconv.Atoi(strvec[0]);

	n, res := new(big.Int).SetString(strvec[1],10)
	g, res := new(big.Int).SetString(strvec[2],10)
	nSq, res := new(big.Int).SetString(strvec[3],10)

	if err == nil && res {
		//compose public key using values informed in the string pubkey
		return &PubKey{KeyLen: l, N: n, G: g, Nsq: nSq}
	} else {
		return nil
	}
}

/*
 * This is an auxiliar function that encapsulates de conversion of a vetor of bytes
 * representing a big.Int number into a literal transcription in string format.
 */
func Bytes2String(bcipher []byte) (string){
	//creates an auxiliar big.Int to manipulate the string
	cipherInt := new(big.Int).SetBytes(bcipher)
	return cipherInt.String()
}

/*
 * This is an auxiliar function that encapsulates de conversion of a string with a
 * literal representation of a big.Int number (base 10) into a vector of bytes in the
 * format required by Gomorph library. 
 */
func String2Bytes(cipher string) ([]byte){
	//creates an auxiliar big.Int to manipulate the string
	cipherInt, err := new(big.Int).SetString(cipher,10)

	if err {
		return cipherInt.Bytes()
	} else {
		return nil
	}
}

/*
 * SmartContract defines the chaincode base structure. All the methods are implemented to
 * return a SmartContrac type.
 */
type SmartContract struct {
}

/*
 * Meter constitutes our key|value struct and implements a single record to manage the 
 * meter public key and measures. All blockchain transactions operates with this type.
 * IMPORTANT: all the field names must start with upper case
 */
type Meter struct {
 	PublicKey		string `json:"publickey"`
	PlainMeasure 	int64  `json:"plainmeasure"`
	EncrypMeasure 	string `json:"encrypmeasure"`
}

/*
 * The Init method is called when the Smart Contract "fabmorph" is instantiated.
 * Best practice is to have any Ledger initialization in separate function.
 * Note that chaincode upgrade also calls this function to reset
 * or to migrate data, so be careful to avoid a scenario where you
 * inadvertently clobber your ledger's data!
 */
func (s *SmartContract) Init(stub shim.ChaincodeStubInterface) sc.Response {
	return shim.Success(nil)
}

/*
 * Invoke function is called on each transaction invoking the chaincode. It
 * follows a structure of switching calls, so each valid feature need to
 * have a proper entry-point.
 */
func (s *SmartContract) Invoke(stub shim.ChaincodeStubInterface) sc.Response {
	// extract the function name and args from the transaction proposal
	fn, args := stub.GetFunctionAndParameters()

	//implements a switch for each acceptable function
	if fn == "registerMeter" {
		//registers a new meter into the ledger
		return s.registerMeter(stub, args)

	} else if fn == "insertMeasurement" {
		//inserts a measurement which increases the meter consumption counter. The measurement
		return s.insertMeasurement(stub, args)
	
	} else if fn == "insertPlainTextMeasurement" {
		//inserts a measurement which increases the meter consumption counter. The measurement
		return s.insertPlainTextMeasurement(stub, args)
	
	} else if fn == "getConsumption" {
		//retrieves the accumulated consumption 
		return s.getConsumption(stub, args)

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
 * SmartContract::registerMeter(...)
 * Does the register of a new meter into the ledger. The meter is the base of the key|value structure.
 * The key constitutes the meter ID. If a cryptographic public key is informed, it indicates that
 * the meter accumulates its measurements using homomorphic cryptography.  
 */
func (s *SmartContract) registerMeter(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 2 {
		return shim.Error("It was expected 2 parameters: <meter id> <public key>")
	}

	//gets the parameter associated with the meter ID and the public key (in string format)
	meterid := args[0]
	strpubkey := args[1] 

	//defines the initial consumption as zero
	plainMeasure := new(big.Int).SetInt64(0)

	//initiates the value of the encrypted measurement
	encrypMeasureString := ""

	//test if strpubkey is a empty string
	if len(strpubkey) > 0 {
		//there is a public key, so we need to encrypt the measurement
		pubkey := String2PubKey(strpubkey)

		if pubkey != nil {
			//encrypts the initial consumption
			encrypMeasure, err := Encrypt(pubkey, plainMeasure.Bytes())

			//test if encryptation had success
			if err != nil {
				return shim.Error("Error on encrypting with the informed public key")
			}			
			encrypMeasureString = Bytes2String(encrypMeasure)
		}
	}

	//creates the meter record
	var meter = Meter{PublicKey: strpubkey, PlainMeasure: plainMeasure.Int64(), EncrypMeasure: encrypMeasureString}

	//encapsulates meter in a JSON structure
	meterAsBytes, _ := json.Marshal(meter)

	//registers meter in the ledger
	stub.PutState(meterid, meterAsBytes)

	//loging...
	fmt.Println("Registering meter: ", meter)

	//notify procedure success
	return shim.Success(nil)
}

func (s *SmartContract) insertMeasurement(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 2 {
		return shim.Error("It was expected 2 parameter: <meter ID> <measurement>")
	}

	//gets the parameter associated with the meter ID and the incremental measurement
	meterid := args[0]

	//try to convert the informed measurement into the format []byte, required by Gomorph
	measurement := String2Bytes(args[1])

	//check if we have success 
	if measurement == nil {
		//measurement is not a proper number
		return shim.Error("Error on veryfing measurement, it is not a proper input")
	}
	
	//retrive meter record
	meterAsBytes, err := stub.GetState(meterid)

	//test if we receive a valid meter ID
	if err != nil || meterAsBytes == nil {
		return shim.Error("Error on retrieving meter ID register")
	}

	//creates Meter struct to manipulate returned bytes
	MyMeter := Meter{}

	//convert bytes into a Meter object
	json.Unmarshal(meterAsBytes, &MyMeter)

	//convert meter public key to the format expected by Gomorph
	pubkey := String2PubKey(MyMeter.PublicKey)

	//compute the new measurement value by using homomorphic adding constant property
	newEncrypMeasure := Add(pubkey, String2Bytes(MyMeter.EncrypMeasure), measurement)  

	//update encrypted measure cipher
	MyMeter.EncrypMeasure = Bytes2String(newEncrypMeasure);

	//encapsulates meter back into the JSON structure
	newMeterAsBytes, _ := json.Marshal(MyMeter)

	//update meter state in the ledger
	stub.PutState(meterid, newMeterAsBytes)

	//loging...
	fmt.Println("Updating meter consumption:", MyMeter)

	//notify procedure success
	return shim.Success(nil)
}

func (s *SmartContract) insertPlainTextMeasurement(stub shim.ChaincodeStubInterface, args []string) sc.Response {

	//validate args vector lenght
	if len(args) != 2 {
		return shim.Error("It was expected 2 parameter: <meter ID> <measurement>")
	}

	//gets the parameter associated with the meter ID and the incremental measurement
	meterid := args[0]

	//try to convert the informed measurement into the format []byte, required by Gomorph
	measurement, err := strconv.ParseInt(args[1], 10, 64)

	//check if we have success 
	if err != nil {
		//measurement is not a proper number
		return shim.Error("Error on veryfing measurement, it is not a proper int64 input")
	}
	
	//retrive meter record
	meterAsBytes, err := stub.GetState(meterid)

	//test if we receive a valid meter ID
	if err != nil || meterAsBytes == nil {
		return shim.Error("Error on retrieving meter ID register")
	}

	//creates Meter struct to manipulate returned bytes
	MyMeter := Meter{}

	//convert bytes into a Meter object
	json.Unmarshal(meterAsBytes, &MyMeter)

	//update the plaintext measurement
	MyMeter.PlainMeasure += measurement;

	//encapsulates meter back into the JSON structure
	newMeterAsBytes, _ := json.Marshal(MyMeter)

	//update meter state in the ledger
	stub.PutState(meterid, newMeterAsBytes)

	//loging...
	fmt.Println("Updating meter plaintext consumption:", MyMeter)

	//notify procedure success
	return shim.Success(nil)
}

func (s *SmartContract) getConsumption(stub shim.ChaincodeStubInterface, args []string) sc.Response {
	//validate args vector lenght
	if len(args) != 1 {
		return shim.Error("It was expected 1 parameter: <meter ID>")
	}

	//gets the parameter associated with the meter ID and the incremental measurement
	meterid := args[0]

	//retrive meter record
	meterAsBytes, err := stub.GetState(meterid)

	//test if we receive a valid meter ID
	if err != nil || meterAsBytes == nil {
		return shim.Error("Error on retrieving meter ID register")
	}

	//return payload with bytes related to the meter state
	return shim.Success(meterAsBytes)
}


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
   Look for a specific vehicle detection event in the ledger and return its changing history.
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
   Look for a specific vehicle detection event in the ledger and count the number of changes in
   its history.
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
   Look for a specific vehicle detection event in the ledger and count the number of changes in
   its history.
*/
func (s *SmartContract) countLedger(stub shim.ChaincodeStubInterface) sc.Response {

	//precisa retornar todos os registros
	resultsIterator, err := stub.GetQueryResult("{\"selector\":{\"plainmeasure\":{\"$gt\": -1}}}")
	//test if iterator is valid
	if err != nil {
		return shim.Error(err.Error())
	}
	//defer iterator closes at the end of the function
	defer resultsIterator.Close()

	//creates a counter
	var counter int64
	counter = 0
	var keys = 0

	//percorre todas a chaves
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
		fmt.Printf("Consulting ledger history, found key %d\n", queryResponse.Key)

		keys++
	}
	// buffer is a JSON array containing records
	var buffer bytes.Buffer
	buffer.WriteString("[")
	buffer.WriteString("\"Counter\":")
	buffer.WriteString(strconv.FormatInt(counter, 10))
	buffer.WriteString("]")

	//loging...
	fmt.Printf("Consulting ledger history, found %d transactions in %d keys\n", counter, keys)

	//notify procedure success
	return shim.Success(buffer.Bytes())
}

/*
 * Execute a free query on the ledger, returning a vector of fill up records (maybe
 * an empty vector). Query string must be informed in args[0].
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

// func TestKeyGen() {
// 	puba, priva, err1 := gaillier.GenerateKeyPair(rand.Reader, 1024)
// 	pubb, privb, err2 := gaillier.GenerateKeyPair(rand.Reader, 2048)
// 	pubc, privc, err3 := gaillier.GenerateKeyPair(rand.Reader, 4096)

// 	if err1 != nil || err2 != nil || err3 != nil {
// 		fmt.Printf("Error Generating Keypair :\n Size:1024  %v\nSize:2048  %v\nSize 4096  %v\n", err1, err2, err3)
// 	}
// 	if puba.KeyLen != 1024 || priva.KeyLen != 1024 {
// 		fmt.Printf("Error generating correct keypair of size 1024 byte got %d want 1024", puba.KeyLen)
// 	}
// 	if pubb.KeyLen != 2048 || privb.KeyLen != 2048 {
// 		fmt.Printf("Error generating correct keypair of size 1024 byte got %d want 2048", puba.KeyLen)
// 	}
// 	if pubc.KeyLen != 4096 || privc.KeyLen != 4096 {
// 		fmt.Printf("Error generating correct keypair of size 1024 byte got %d want 4096", puba.KeyLen)
// 	}

// }

// func TestEncryptDecrypt() {

// 	case1 := new(big.Int).SetInt64(9132)
// 	case2 := new(big.Int).SetInt64(1492)

// 	fmt.Printf("Dado: %i\n", case1)

// 	pub, priv, err := gaillier.GenerateKeyPair(rand.Reader, 512)

// 	if err != nil {
// 		fmt.Printf("Error Generating Keypair")
// 	}
// 	encCase1, errCase1 := gaillier.Encrypt(pub, case1.Bytes())
// 	encCase2, errCase2 := gaillier.Encrypt(pub, case2.Bytes())

// 	fmt.Printf("Dado encriptado: %v\n", encCase1)

// 	if errCase1 != nil || errCase2 != nil {
// 		fmt.Printf("Error encrypting keypair %v \n %v", errCase1, errCase2)
// 	}

// 	d1, errDec1 := gaillier.Decrypt(priv, encCase1)
// 	d2, errDec2 := gaillier.Decrypt(priv, encCase2)

// 	decCase1 := new(big.Int).SetBytes(d1)
// 	decCase2 := new(big.Int).SetBytes(d2)
// 	if decCase1.Cmp(case1) != 0 || decCase2.Cmp(case2) != 0 {
// 		fmt.Printf("Error Decrypting the message %v \n %v", errDec1, errDec2)
// 	}

// }

func TestAdd() {
	case1 := new(big.Int).SetInt64(1)
	case2 := new(big.Int).SetInt64(1)

	pub, priv, err := GenerateKeyPair(rand.Reader, 512)

	if err != nil {
		fmt.Printf("Error Generating Keypair")
	}
	//Encrypt
	encCase1, err1 := Encrypt(pub, case1.Bytes())
	encCase2, err2 := Encrypt(pub, case2.Bytes())

	if err1 != nil || err2 != nil {
		fmt.Printf("Error Encrypting Integers")
	}

	res := Add(pub, encCase1, encCase2)

	corr := new(big.Int).SetInt64(2)

	decRes, err := Decrypt(priv, res)
	if err != nil {
		fmt.Printf("Failed to Decrypt Result got %v want %v with Error : %v", decRes, corr, err)
	}

	resB := new(big.Int).SetBytes(decRes)

	if resB.Cmp(corr) != 0 {
		fmt.Printf("Failed to Add two ciphers got %v want %v", resB, corr)
	}

}

/*
 * The main function starts up the chaincode in the container during instantiate
 */
func main() {

	//DESCOMENTAR ESSE BLOCO QUANDO FOR INSERIR NO FABRIC
	if err := shim.Start(new(SmartContract)); err != nil {
	    fmt.Printf("Error starting SmartContract chaincode: %s\n", err)
	}

	//Chaincode codetest
	//fmt.Printf("%s\n", getSpeed("77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,77,120,73,120,71,120,70,120,68,120,66,120,62,120,58,120,49,120,42,120,32,120,19,120,0,120,236,120,212,120,185,120,160,120,132,120,103,120,72,120,36,120,244,120,191,120,134,123,76,125,22,126,234,127,196,128,166,129,140,130,120,131,106,133,96,133,88,134,82,134,83,135,84,135,92,135,97,135,104,135,104,135,104,134,95,134,85,128,66,125,45,119,15,112,230,102,178,89,118,72,51,52,246,25,192,251,159,221,145,191,159,157,191,122,235,75,19,25,55,222,77,159,91,89,98,27,98,226,99,176,103,133,107,97,115,67,125,47,142,35,162,26,187,26,209,27,236,34,0,44,20,54,40,63,53,66,71,67,86,64,106,55,134,40,174,21,219,247,13,211,63,161,109,100,153,30,189,214,221,147,243,100,6,79,16,86,22,117,22,163,18,214,17,2,7,34,254,50,246,50,236,42,225,32,215,22,197,19,183,21,167,30,153,44,141,67,130,90,120,119,109,145,98,168,87,188,77,206,71,225,71,237,71,0,72,19,81,49,81,86,81,135,81,192,79,252,76,56,73,106,71,155,70,195,70,230,70,0,70,18,70,28,66,31,56,33,37,31,17,27,248,19,228,9,218,255,219,245,234,235,5,218,44,203,87,186,135,172,179,158,220,147,0,136,29,124,50,114,65,100,75,90,85,81,89,79,91,78,92,78,92,80,92,82,92,82,92,77,88,68,82,60,72,50,62,43,51,38,31,33,11,31,245,31,218,31,196,31,167,25,147,10,125,244,111,222,104,195,103,175,110,165,121,168,138,190,148,226,149,14,140,64,130,114,120,163,113,206,116,244,126,17,148,37,172,49,193,59,215,63,234,64,248,64,6,64,17,64,31,64,42,61,60,56,74,51,90,42,108,32,125,22,145,4,165,239,185,214,201,184,220,154,233,124,247,94,1,68,11,48,21,31,28,21,36,20,38,27,44,37,44,47,48,49,50,47,53,42,54,38,56,38,60,44,60,60,63,84,66,115,66,155,68,189,68,219,71,244,71,8,75,28,75,48,76,64,77,82,78,100,78,118,78,137,78,156,78,176,78,196,78,216,78,236,78,0,78,20,78,39,78,51,78,61,78,71,78,81,78,91,78,96,78,99,78,102,78,103,78,105,78,106,78,108,78,109,78,111,78,111,78,112,78,113,78,113,78,113,78,113,78,113,78,113,78,113,78,114,78,114,78,115,78,115,78,116,78,116"))

	//TestKeyGen();

	//TestEncryptDecrypt();

	//TestAdd();

	// pub, _, _ := GenerateKeyPair(rand.Reader, 512)

	// //if err != nil

	// spub := PubKey2String(pub)

	// fmt.Println(spub)

	// newpub := String2PubKey(spub)

	// fmt.Println(newpub)
}
