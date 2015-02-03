#! /usr/bin/python
# -*- coding: utf-8 -*-

#    Copyright 2014 Philippe THIRION
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import wsclient
import wsserver

server = wsserver.wsserver()
client = wsclient.wsclient()

# Handshaking
ext = {}
ext["Host"] = "sip//ws.example.com"
ext["Origin"] = "http://www.example.com"
ext["Sec-WebSocket-Protocol"] = "sip"
client.setExtensions(ext)
client.sendHandshake()
if client.status() != 6:
    print "Client error: handshake request"
    exit()
buffer = client.result()
print buffer
print
server.dataRecv(buffer)
if server.status() != 1:
    print "Server error: handshake request"
    exit()
buffer = server.result()
print buffer
print
client.dataRecv(buffer)
if client.status() != 1:
    print "Client error: handshake response failed"
    exit()
print "Handshaking terminated"
print

# Framing client to server
register = ["REGISTER sip:localhost:11000 SIP/2.0",
"From: <sip:1002@localhost:11000>;tag=D86AF42D-8A1E-4D1E-A994-49E58D4B0B1B-1",
"To: <sip:1002@localhost:11000>",
"Call-ID: BC7647DD-A1AD-49BD-AF1C-BC34BE432310-1@127.0.0.1",
"CSeq: 1 REGISTER",
"Content-Length: 0",
"Subject: éèàçê",
"Via: SIP/2.0/UDP 127.0.0.1:50976;branch=z9hG4bK8B453B7E-70EB-4065-B418-F428335BEFCE-1",
"Contact: <sip:127.0.0.1:50976>",
"Expires: 3600",
""]

bregister = "\r\n".join(register)
#print bregister
#print
client.sendData(bregister)
if client.status() != 3:
    print "Client error: frame encoding"
    exit()
buffer = client.result()
server.dataRecv(buffer)
if server.status() != 8:
    print "Server error: frame decoding"
    exit()
buffer = server.result()
#print buffer
#print
if buffer != bregister:
    print "Error: client encoding/server decoding"
    print bregister
    print '---'
    print buffer
    exit()

print "Framing client to server OK"
print

# Framing server to client
    
register_200 = ["SIP/2.0 200 OK",
"From: <sip:1002@localhost:11000>;tag=D86AF42D-8A1E-4D1E-A994-49E58D4B0B1B-1",
"To: <sip:1002@localhost:11000>;tag=8A878506-2CB3-4D3D-90CC-193FD41B41DF-11",
"Call-ID: BC7647DD-A1AD-49BD-AF1C-BC34BE432310-1@127.0.0.1",
"CSeq: 2 REGISTER",
"Subject: éèàçê",
"Via: SIP/2.0/UDP 127.0.0.1:50976;branch=z9hG4bK8B453B7E-70EB-4065-B418-F428335BEFCE-2;received=127.0.0.1",
"Expires: 1800",
"Contact: <sip:127.0.0.1:50976>;expires=1800",
"Content-Length: 0",
""]

b200 = "\r\n".join(register_200)
server.sendData(b200)
if server.status() != 3:
    print "Server error: frame encoding"
    exit()
buffer = server.result()
client.dataRecv(buffer)
if client.status() != 8:
    print "Client error: frame decoding"
    exit()
buffer = client.result()
if buffer != b200:
    print "Error: server encoding/client decoding"
    print b200
    print '---'
    print buffer
    exit()
print "Framing server to client OK"


