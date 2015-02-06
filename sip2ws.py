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


# This module is a bidirectional SIP UDP to Websocket converter

"""
-----------------           -----------
           |     |         |           |<========> Softphone SIP/UDP
SIP server | WS  |<=======>| sip2ws.py |<========> Softphone SIP/UDP
or proxy   | port|         |           |<========> Softphone SIP/UDP
           |     |         |           |<========> Softphone SIP/UDP
-----------------           -----------
"""

# Configuration
# -----------------------------------------------------
# Softphone: UDP - proxy = SERVER_HOST:SERVER_PORT
# SIP server: websocket port = CLIENT_HOST:CLIENT_PORT
SERVER_HOST, SERVER_PORT = '0.0.0.0', 8060
CLIENT_HOST, CLIENT_PORT = '172.26.158.24', 5060

import wsclient
import SocketServer
import re
import socket
import threading
import string

rx_via = re.compile("^Via:")
rx_contact = re.compile("^Contact:")
rx_record_route = re.compile("^Record-Route:")
rx_viaproto = re.compile("SIP/2.0/([^ ]*)")
rx_transportproto = re.compile("transport=([^;$> ]*)")

context = {}
recordroute = ""
#topvia = ""

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
            
        
    def _data2list(self,data):
        return data.split("\r\n")
        
    def _list2data(self,list):
        return "\r\n".join(list)
            
    def _filter(self,data,proto):
        #list = data.split("\r\n")
        list = self._data2list(data)
        size = len(list)
        for index in range(size):
            line = list[index]
            if rx_via.search(line):
                md = rx_viaproto.search(line)
                if md:
                    p = md.group(1)
                    list[index] = line.replace(p,string.upper(proto))
            if (index == 0) or rx_contact.search(line) or rx_record_route.search(line):
                md = rx_transportproto.search(line)
                if md:
                    p = md.group(0)
                    proto1 = "transport=%s" % proto
                    list[index] = line.replace(p,string.lower(proto1))
        #list.append("")
        #return "\r\n".join(list)
        return self._list2data(list)
    
    def _clean_headers(self,data):
        # record-route and top via
        vias = []
        listin = self._data2list(data)
        listout = []
        for line in listin:
            # erase all record-route
            if rx_record_route.search(line):
                pass
            elif rx_via.search(line):
                vias.append(line)
            else:
                listout.append(line)
        # erase top via except if only one
        if len(vias) > 1:
            vias.pop(0)
        vias.reverse()
        for str in vias:
            listout.insert(1,str)
        # insert record-route
        listout.insert(1,recordroute)
        return self._list2data(listout)
        
    def receive(self,data):
        if self.ws:
            self.ws.dataRecv(data)
            status = self.ws.status()
            if status == 1:
                print "handshake OK"
            elif status == 2:
                print "handshake NOK"
            elif status == 8:
                # receive decoded frame 
                wsdata = self.ws.result()
                wsdata = self._clean_headers(wsdata)
                wsdata = self._filter(wsdata,"UDP")
                print "received: \n%s" % wsdata
                #print self.client_address
                self.socket.sendto(wsdata,self.client_address)
            elif status == 4:
                # sending PONG
                print "received PING - sending PONG"
                wsdata = self.ws.result()
                self.csock.send(wsdata)
            elif status == 5:
                # sending CLOSE
                print "received CLOSE - sending CLOSE"
                wsdata = self.ws.result()
                self.csock.send(wsdata)
                del context[self.client_address]
            else:
                print "receive: unexpected status = %d" % status
                
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
                        
            """
            list = self._data2list(data)
            list.insert(1,recordroute)
            #list.insert(1,)
            data = self._list2data(list)
            """     
            data = self._filter(data,"WS")
            self.ws.sendData(data)
            if self.ws.status() == 3:
                print "send:\n%s" % data
                wsdata = self.ws.result()
                self.csock.send(wsdata)

if __name__ == "__main__":
    hostname = socket.gethostname()
    print hostname
    ipaddress = socket.gethostbyname(hostname)
    print ipaddress
    recordroute = "Record-Route: <sip:%s:%d;lr>" % (ipaddress,SERVER_PORT)
    #topvia = "Via: SIP/2.0/UDP %s:%d" % (ipaddress,SERVER_PORT)
    server = SocketServer.UDPServer((SERVER_HOST, SERVER_PORT), UDPHandler)
    server.serve_forever()