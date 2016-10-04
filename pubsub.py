#!/usr/bin/env python

from ethereum import tester
from ethereum import utils
from ethereum import slogging
from ethereum import _solidity
from ethereum._solidity import get_solidity
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Cipher import PKCS1_v1_5
import rlp

#slogging.configure(':DEBUG,eth.vm:TRACE')

state = None
publisher_contracts = dict()  # key: contract_owner, value: contract(abi)
subscriber_contracts = dict() # key: contract_ownder, value: contract(abi)
num_publishers = 1
num_subscribers = 1 
logs=[]
m_key = None

# -- code to generate random private keys and the corresponding account (public
# address)
#accounts = []
#keys = []
#for in range(..):
#    keys.append(utils.sha3(str(i)))
#    accounts.append(utils.privtoaddr(keys[-1]))

def main():
    global state
    state = tester.state()
    path="/598/ethereumlab/ece598fall2016/pubsub.sol"
    
    # params : (size of request queue, timeout-limit in number of blocks)
    constructor_parameters=[1000, 20]

    # all contracts are initiated with a 100 ether starting endowment
    # init publisher contract
    publisher_contracts[tester.k2] = state.abi_contract(None,
            sender=tester.k2, endowment=100*utils.denoms.ether,\
            language='solidity', path=path, log_listener = lambda x:\
            logs.append(x), constructor_parameters=constructor_parameters, contract_name='publisher')

    # init subscriber contract
    subscriber_contracts[tester.k1] = state.abi_contract(None,
            sender=tester.k1, endowment=100*utils.denoms.ether,\
            language='solidity', path=path, log_listener = lambda x:\
            logs.append(x), contract_name='subscriber')

    # make all account balances 100 ether
    state.block.set_balance(tester.a2, 100 * utils.denoms.ether)
    state.block.set_balance(tester.a1, 100 * utils.denoms.ether)

def showBalance(when):
    print('\n\n-----')
    print("%s balance:"%when)
    print("Publisher: %.2f ethers"%(state.block.get_balance(tester.a2)/(1.0*10**18)))
    print("Publisher-contract: %.2f ethers"%(state.block.get_balance(publisher_contracts[tester.k2].address)/(1.0*10**18)))
    print("Subscriber: %.2f ethers"%(state.block.get_balance(tester.a1)/(1.0*10**18)))
    print("Subscriber-contract: %.2f ethers"%(state.block.get_balance(subscriber_contracts[tester.k1].address)/(1.0*10**18)))
    print('-----\n\n')

def publishStump():
    """
    publisher initiates a transaction to the his contract to publish a
    stump. Fails if the sender if not the publisher
    """
    contract = publisher_contracts[tester.k2]
    contract.publishStump(45, 1 * utils.denoms.ether, "Snapchat unveils $130 and ...", sender=tester.k2)
    contract.publishStump(198, 7 * utils.denoms.ether, "Messi ruled out for ...", sender=tester.k2)
    contract.publishStump(244, 33 * utils.denoms.ether, "Jack the Ripper's horrifying murders ...", sender=tester.k2)

def getStumps():
    """
    subscriber looks up the storage to find all the available stumps from the
    publisher of choice
    """
    publisher_choice = tester.k2
    contract = publisher_contracts[publisher_choice]
    ids = contract.getStumpIds()

    print("Stumps from publisher ", tester.k2.encode('hex'))
    for _id in ids:
        print(contract.getStumpData(_id)+" Price: %.2f ethers"%(contract.getStumpPrice(_id)/(1.0*10**18)))

def purchase(sid):
    """
    subscriber sends a transaction to the publisher contract to purchase a
    stump; pays the corresponding price. Stump-id is the input
    """
    publisher_choice = tester.k2
    contract = publisher_contracts[publisher_choice]
    id_choice = contract.getStumpIds()[sid]   # todo: check for valid sid
    price = contract.getStumpPrice(id_choice)  # in wei
                
    # hack. [todo]: move the subscriber key to a subscriber specific data
    # structure
    global m_key
    
    # the subscriber generates a RSA pair. Public key is provided to the
    # contract. The link to the full article is then encrypted by the publisher
    # using this public key and put on the blockchain in the subscriber contract
    if m_key is None: m_key = RSA.generate(1024, Random.new().read)
    m_pbkey = m_key.publickey().exportKey() 
    m_contract_addr = subscriber_contracts[tester.k1].address

    # send tx (price is in wei already)
    contract.purchase(id_choice, m_contract_addr, m_pbkey, value=price, sender=tester.k1)

# request type received by publisher
class Request:
    def __init__(self, _sid, _reqt, _addr, _pbkey):
        self.sid = _sid
        self.reqt = _reqt
        self.addr = _addr
        self.pbkey = _pbkey

    @property
    def sid(self):
        return self.sid

    @property
    def reqt(self):
        return self.reqt

    @property
    def addr(self):
        return self.addr

    @property
    def pbkey(self):
        return self.pbkey

def getRequests():
    """
    publisher looks up the storage to find all the 'pending' requests in queue
    of publisher contract
    """
    publisher_id = tester.k2
    contract = publisher_contracts[publisher_id]
    numPending = contract.getNumPending()
    requests = []
    print("Publisher contract has %d pending requests"%numPending)

    for i in range(numPending):
        # data format : 
        # 32-bytes stump id
        # 32-bytes request time
        # 20-bytes contract address
        # variable bytes public key of contract
        data = contract.getRequestsSerialized(i)
        _sid = int(data.encode('hex')[0:64], 16)
        _reqt = int(data.encode('hex')[64:128], 16)
        _addr = data.encode('hex')[128:168]
        _pbkey = data.encode('hex')[168:].decode('hex')
        print("Publisher retrieved request : stump id(%d), request time(%d), contract address(%s) pbkey(%s)"%(_sid, _reqt, _addr, _pbkey))
        requests.append(Request(_sid, _reqt, _addr, _pbkey))

    return requests

def get_full_link(sid):
    """
    gets full link for stump-id
    """
    #todo : this is just a demo as of yet
    if sid == 45: return "Snapchat unveils $130 and rebrands as Snap, Inc."
    if sid == 198: return "Messi ruled out for three weeks with groin injury."
    if sid == 244: return "Jack the Ripper's horrifying murders terrorize London."

def handleRequests(requests):
    """
    publisher serves each request by sending as a transaction, the (encrypted)
    link to the full article to the publisher contract. The publisher contract
    then releases the (escrow) money to the publisher account and sends the link
    to the subscriber's contract address where it is put in storage
    """
    publisher_id = tester.k2
    contract = publisher_contracts[publisher_id]

    for request in requests:
        sid = request.sid
        # this function should check if sid is valid. For now, we assume it is
        #check_sid()    
        full_link = get_full_link(sid)

        # encrypt the full link with the public key of the subscriber
        cipher = PKCS1_v1_5.new(RSA.importKey(request.pbkey))
        ciphertext = cipher.encrypt(full_link)
            
        # send tx
        contract.completeRequest(sid, request.addr, ciphertext, sender=publisher_id)

def readLinks():
    """
    subscriber reads his contract to get the (encrypted) links from different
    publishers
    """
    subscriber_id = tester.k1
    contract = subscriber_contracts[subscriber_id]
    publisher_choice = tester.a2

    num_links = contract.getNumberLinks(publisher_choice)
    print("Subscriber has %d links from publisher %s"%(num_links,\
        tester.k2.encode('hex')))

    for i in range(num_links):
        ciphertext = contract.getLink(publisher_choice, i)
        cipher = PKCS1_v1_5.new(m_key)
        plaintext = cipher.decrypt(ciphertext, Random.new().read)
        print('Full link from publisher: ', plaintext)

def reclaim(sid):
    """
    subscriber sends a transaction to the publisher contract to get a refund if
    the publisher doesn't supply the requested data within timeout limit
    """
    subscriber_id = tester.k1
    publisher_choice = tester.k2
    contract = publisher_contracts[publisher_choice]
    
    # assuming we have a pending request for this stump id
    id_choice = contract.getStumpIds()[sid]

    # send tx
    # send stump-id and subscriber contract address as identifying data
    contract.reclaim(id_choice, subscriber_contracts[subscriber_id].address,\
            sender=subscriber_id)

def exec1():
    """
    Normal execution 
    """
    publishStump()
    getStumps()
    purchase(0)
    state.mine(1) # mine a block
    showBalance('Intermediate')
    requests = getRequests()
    handleRequests(requests)
    showBalance('Intermediate')
    purchase(1)
    purchase(2)
    showBalance('Intermediate')
    requests = getRequests()
    handleRequests(requests)
    readLinks()
      
def exec2():
    """
    Publisher doesn't respond within time limit
    """
    publishStump()
    getStumps()
    purchase(0)
    purchase(1)
    state.mine(30) # mine blocks
    showBalance('Intermediate')
    reclaim(1)
    # publisher wakes from slumber
    requests = getRequests()
    handleRequests(requests)
    readLinks()

if __name__=="__main__":
    assert get_solidity() is not None, "Solidity compiler not available"
    main()
    state.mine(1) # mine a block
    showBalance('Initial')
    exec2()
    showBalance('Final')
    #print(logs)
