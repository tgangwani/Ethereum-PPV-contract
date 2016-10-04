Introduction
==============
Pay-Per-View (PPV) is a type of service where content makers and distributors can publish their feeds, and subscribers have an option to pay selectively, as per their liking. Publishers decide the price for each feed and subscribers can pay the publishers only for the feeds they want access to.

This Ethereum smart contact implements a version of the aforementioned distribution paradigm. There are two types of contracts - publisher and subscriber. As the names suggest, the former is created by a publisher or content creator, while the latter is created by subscribers or users.

Full Report
==============
An IPython notebook embeds the full contract description and test executions.
It is stored as a public Gist. One way to access is as follows-

Go to http://nbviewer.jupyter.org/ and enter the Gist-id:
"https://gist.github.com/tgangwani/d6bd7b3c04dc4a3b68e0b83dbb46359d"


Files
==============
1) pubsub.sol which implements the contract in Solidity

2) pubsub.py which does a test execution on Pyethereum


How to run
==============
Change the path in pubsub.py (line 34.) to point to the smart contract. At line
271., exec2 can be replaced by exec1 to simulate a different execution
