#! /usr/bin/python
# -*- coding: utf-8 -*-

#    Copyright 2015 Philippe THIRION
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

SERVER_HOST, SERVER_PORT = '0.0.0.0', 5060
CLIENT_HOST, CLIENT_PORT = '172.26.158.24', 5060

import wsclient
import SocketServer
import re
import socket
import threading
import string

rx_via = re.compile("^Via:")
rx_contact = re.compile("^Contact:")
rx_viaproto = re.compile("SIP/2.0/([^ ]*)")
rx_transportproto = re.compile("transport=([^;$>]*)")

context = {}

class WSListener(threading.Thread):
    def __init__(self,csock,parent):
        threading.Thread.__init__(self)
        self.csock = csock
        self.parent = parent
    def run(self):
        while(True):
            data = self.csock.recv(4096)
            self.parent.receive(data)
        

class UDPHandler(SocketServer.BaseRequestHandler): 
        
    def _connect(self):
        # open client socket
        self.csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.csock.connect((CLIENT_HOST,CLIENT_PORT))
        thread = WSListener(self.csock,self)
        thread.daemon = True
        thread.start()
        # ws handshaking
        self.ws = wsclient.wsclient()
        extension = {}
        extension["Host"] = "sip//ws.example.com"
        extension["Origin"] = "http://www.example.com"
        extension["Sec-WebSocket-Protocol"] = "sip"
        self.ws.setExtensions(extension)
        self.ws.sendHandshake()
        if self.ws.status() == 6:
            wsdata = self.ws.result()
            self.csock.send(wsdata)
            context[self.client_address] = (self.csock,self.ws)
        else:
            print "handshake request issue"
            
    def _filter(self,data,proto):
        list = data.split("\r\n")
        size = len(list)
        for index in range(size):
            line = list[index]
            if rx_via.search(line):
                md = rx_viaproto.search(line)
                if md:
                    p = md.group(1)
                    list[index] = line.replace(p,string.upper(proto))
            if rx_contact.search(line) or (index == 0):
                md = rx_transportproto.search(line)
                if md:
                    p = md.group(0)
                    proto1 = "transport=%s" % proto
                    list[index] = line.replace(p,string.lower(proto1))
        #list.append("")
        return "\r\n".join(list)
        
    def receive(self,data):
        if self.ws:
            self.ws.dataRecv(data)
            status = self.ws.status()
            if status == 1:
                print "handshake OK"
            elif status == 2:
                print "handshake NOK"
            elif status == 8:
                wsdata = self.ws.result()
                wsdata = self._filter(wsdata,"UDP")
                print "received: \n%s" % wsdata
                #print self.client_address
                self.socket.sendto(wsdata,self.client_address)
                
    def handle(self):
        data = self.request[0]
        if len(data) < 5:
            return
        print "UDPHandler handle"
        self.socket = self.request[1]
        #print self.client_address
        if not context.has_key(self.client_address):
            self._connect()
        else:
            (self.csock,self.ws) = context[self.client_address]
            data = self._filter(data,"WS")
            self.ws.sendData(data)
            if self.ws.status() == 3:
                print "send:\n%s" % data
                wsdata = self.ws.result()
                self.csock.send(wsdata)

if __name__ == "__main__":
    server = SocketServer.UDPServer((SERVER_HOST, SERVER_PORT), UDPHandler)
    server.serve_forever()