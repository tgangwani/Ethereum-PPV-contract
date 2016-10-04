pragma solidity ^0.4.0;

contract subscriber {
    
    // events for logging
    event e_requestComplete(string str, address from);

    address public owner;
    mapping (address => bytes[]) encryptedLinks;

    function subscriber() {
      owner = msg.sender;
    }

    // request completed by publisher, put in storage
    function completeRequest(address from, bytes data) {
      bytes[] links = encryptedLinks[from];
      links.length += 1;
      links[links.length-1] = data;
      e_requestComplete("Subscriber request completed by publisher", from);
    }

    // subscriber reads from storage
    function getNumberLinks(address from) constant returns (uint) {
      return encryptedLinks[from].length;
    }

    // subscriber reads from storage
    function getLink(address from, uint offset) constant returns (bytes b) {
      bytes[] links = encryptedLinks[from];
      b = links[offset];
    }

    function refund() payable {
    }
}

contract publisher {
    
    // events for logging
    event e_purchaseFail(uint id, address c, bytes pbkey, string s);
    event e_purchaseSuccess(uint id, address c, bytes pbkey);
    event e_publishStump(uint id, bytes data, uint price);
    event e_refundClaim(address from, uint id, string status);

    struct stump {
      bytes data;
      uint price;
    } 
  
    struct requestor {
      uint stumpId;
      uint requestTime;
      address reqContract;
      bytes pbkey;
    }

    address public owner;
    uint public escrow;
    uint public timeout;
    uint[] ids;
    mapping (uint => stump) stumps;   // stumps in plain-text 
    requestor[] requestors;   // circular queue of length specified in the constructor 
    uint private head;
    uint private tail;
  
    function publishStump(uint id, uint price, bytes data) { 
      if(msg.sender != owner) return;
      
      // publish a new stump
      ids.length += 1;
      ids[ids.length-1] = id; 
      stumps[id].data = data;
      stumps[id].price = price;
      e_publishStump(id, data, price);
    }

    function getStumpIds() constant returns (uint[]) {
      return ids;
    }

    // read the stump data
    function getStumpData(uint id) constant returns (bytes) {
      if(stumps[id].data.length == 0) return;
      return stumps[id].data;
    }

    // read the stump price
    function getStumpPrice(uint id) constant returns (uint) {
      if(stumps[id].price == 0) return;
      return stumps[id].price;
    }

    // constructor
    function publisher(uint size, uint limit) {
      owner = msg.sender;
      requestors.length = size;
      timeout = limit;
    }

    // call by publisher to get the number of pending requests
    function getNumPending() constant returns (uint) {
      return ((head + requestors.length - tail) % requestors.length);
    }
  
    // call by publisher to get requests to serve
    function getRequestsSerialized(uint offset) constant returns (bytes b) {
      bytes pbkey = requestors[tail+offset].pbkey;
      uint size = 32 + 32 + 20 + pbkey.length;

      // serialize the requestor struct (at offset) into a single bytes array of
      // size=size and return
      b = new bytes(size);
      uint pos = 0;
      uint i = 0;
      
      bytes memory _b = uint256ToBytes(requestors[tail+offset].stumpId);
      for (i = 0; i < 32; i++)
        b[pos++] = _b[i];

      _b = uint256ToBytes(requestors[tail+offset].requestTime);
      for (i = 0; i < 32; i++)
        b[pos++] = _b[i];

      _b = addressToBytes(requestors[tail+offset].reqContract);
      for (i = 0; i < 20; i++)
        b[pos++] = _b[i];

      for (i = 0; i < pbkey.length; i++)
        b[pos++] = pbkey[i];
    }

    // call made by a subscriber to purchase stump
    function purchase (uint id, address c, bytes pbkey) payable {

      // requestor queue is full, can't take purchase requests, return money
      if((head + 1) % requestors.length == tail) {
        e_purchaseFail(id, c, pbkey, "requestor queue is full");
        if(!msg.sender.send(msg.value)) throw;
        return;
      }
    
      // stump with id not found, return money 
      if(stumps[id].data.length == 0) {
        e_purchaseFail(id, c, pbkey, "stumpId not found");
        if(!msg.sender.send(msg.value)) throw;
        return;
      }

      // insufficient payment, return money
      if(msg.value < stumps[id].price) {
        e_purchaseFail(id, c, pbkey, "insufficient money");
        if(!msg.sender.send(msg.value)) throw;
        return;
      }

      // add to the circular queue
      requestor R = requestors[head];
      R.stumpId = id;
      R.reqContract = c;
      R.pbkey = pbkey;
      R.requestTime = block.number;
    
      escrow += msg.value;

      // move forward the head
      head = (head + 1) % requestors.length;
      e_purchaseSuccess(id, c, pbkey);
    }
    
    // called by publisher to complete the purchase request
    function completeRequest(uint sid, address reqAddr, bytes data) {
      if(msg.sender != owner) return;

      // force the publisher to complete requests in order
      if(reqAddr != requestors[tail].reqContract) return;
      if(sid != requestors[tail].stumpId) return;

      // pay the publisher first. This protects against any malicious
      // implementations of the completeRequest() in subscriber contract
      uint price = getStumpPrice(sid);
      if(!owner.send(price)) throw; 
    
      // call the subscriber contract 
      (subscriber(reqAddr)).completeRequest(owner, data);
      
      // pop from queue
      tail = (tail + 1) % requestors.length; 
    }

    // called by subscriber to get refund on time expire
    function reclaim(uint sid, address reqAddr) {
      
      uint num_elements = (head + requestors.length - tail) % requestors.length;
      if(num_elements==0) {
        e_refundClaim(msg.sender, sid, "Illegal refund claim. No pending requestors");
        return;
      }

      uint price;
      uint start = tail;
      bool refunded = false;
      while(num_elements > 0)
      {
        // identify the request and process refund
        if(requestors[start].reqContract == reqAddr && requestors[start].stumpId == sid) {
          if(block.number > requestors[start].requestTime + timeout) {
            price = getStumpPrice(sid);
            (subscriber(reqAddr)).refund.value(price)();
            e_refundClaim(msg.sender, sid, "Refund successful");
            refunded = true;
            break;
          } 
        }
        
        start = (start + 1) % requestors.length;
        num_elements--;
      }

      if(refunded) {

        // since the requests are arranged in order, the request prior to the one
        // refund are expired as well. So  we refund them as well
        uint start2 = tail;
        while(start2 != start) {
          if(block.number <= requestors[start2].requestTime + timeout) throw;
          price = getStumpPrice(requestors[start2].stumpId);
          (subscriber(requestors[start2].reqContract)).refund.value(price)();

          start2 = (start2 + 1) % requestors.length;
        }
      
        // move the tail ahead to capture loss (refund) of requests
        tail = (start + 1) % requestors.length;
      }

    }

    // helper functions
    function uint256ToBytes(uint256 x) internal returns (bytes b) {
        b = new bytes(32);
        assembly { mstore(add(b, 32), x) }
    }

    function addressToBytes(address x) internal returns (bytes b) {
        b = new bytes(20);
        for (uint i = 0; i < 20; i++)
          b[i] = byte(uint8(uint(x) / (2**(8*(19 - i)))));
    }
}
