# PyWebsocketClient 

Websocket client module
=======================

                     -------------------
    dataRecv() ---->|                   |<----- status()
    state() ------->|                   |<----- result()
                    |                   |<----- sendData()
                    |                   |<----- sendHandshake()
                     -------------------


- dataRecv() : data received from network (handshake response or data frame)
- status() : what to do with processing result (i.e send to network, send to application ...)
- result() : processing result
- sendSata() : data to be encoded before sent to network
- state() : state of connection (readyState see websocket API)
- sendPing()
- sendClose()
- sendHandshake(): send handshake request
- setExtensions(): Add extra headers for handshake request

readyState
==========
- CONNECTING = 0
- OPEN = 1
- CLOSING = 2
- CLOSED = 3

status
======
-   0   Nothing to do
-   1   Handshake response OK - Nothing to do
-   2   Handshake response not OK - Nothing to do
-   3   Data (frame encoded) to network
-   4   Pong (After receiving a Ping) to network
-   5   Close (After receiving close) to network
-   6   Send HandShake request to network
-   8   Data (frame decoded) to application
   
