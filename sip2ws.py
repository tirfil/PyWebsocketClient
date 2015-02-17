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
CLIENT_HOST, CLIENT_PORT = '172.26.174.134', 5262

import wsclient
import SocketServer
import re
import socket
import threading
import string
import sys

rx_via = re.compile("^Via:")
rx_contact = re.compile("^Contact:")
rx_record_route = re.compile("^Record-Route:")
rx_viaproto = re.compile("SIP/2.0/([^ ]*)")
rx_transportproto = re.compile("transport=([^;$> ]*)")

rx_received = re.compile("received=")
rx_route = re.compile("^Route:")

rx_branch = re.compile("branch=([^;$ ]*)")
rx_response = re.compile("^SIP/2.0");
rx_rport = re.compile("rport$")

context = {}
#recordroute = ""
#topvia = ""
ipaddress = ""

class WSListener(threading.Thread):
    def __init__(self,csock,parent):
        threading.Thread.__init__(self)
        self.csock = csock
        self.parent = parent
    def run(self):
        while(True):
            data = self.csock.recv(4096)
            if len(data) > 4:
                self.parent.receive(data)
        

class UDPHandler(SocketServer.BaseRequestHandler): 
        
    def _connect(self):
        # open client socket
        try:
            self.csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error:
            print 'Failed to create socket'
            return
        try:
            self.csock.connect((CLIENT_HOST,CLIENT_PORT))
        except:
            print 'Cannot connect'
            return
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
            
    def _filter_proto(self,data,proto):
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
            if (index == 0):
                md = rx_transportproto.search(line)
                if md:
                    p = md.group(0)
                    proto1 = "transport=%s" % proto
                    list[index] = line.replace(p,string.lower(proto1))
                #else:
                #    list[index] = line.replace(" SIP/2.0",";transport=%s SIP/2.0" % string.lower(proto))
            if rx_contact.search(line) or rx_record_route.search(line):
                md = rx_transportproto.search(line)
                if md:
                    p = md.group(0)
                    proto1 = "transport=%s" % proto
                    list[index] = line.replace(p,string.lower(proto1))
        #list.append("")
        #return "\r\n".join(list)
        return self._list2data(list)
        
    def _process_headers(self,data,address,send):
        listin = self._data2list(data)
        listout = []
        if send:
            for line in listin:
                if not rx_route.search(line) and not rx_record_route.search(line):
                    listout.append(line)
        else:
            topvia = True
            for line in listin:
                if topvia and rx_via.search(line):
                    topvia = False
                    if not rx_received.search(line):
                        line += ";received=%s;rport=%d" % address
                    listout.append(line)
                elif not rx_route.search(line) and not rx_record_route.search(line):
                    listout.append(line)
            rr = "Record-Route: <sip:%s:%d;lr>" % address
            listout.insert(1,rr)
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
                #address = self.csock.getsockname()
                wsdata = self._process_headers(wsdata,(ipaddress,SERVER_PORT),False)
                wsdata = self._filter_proto(wsdata,"UDP")
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
            if self.ws.state() > 0:
                address = self.csock.getsockname()
                data = self._process_headers(data,address,True)
                data = self._filter_proto(data,"WS")
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
    if ipaddress == "127.0.0.1":
        ipaddress = sys.argv[1]
    server = SocketServer.UDPServer((SERVER_HOST, SERVER_PORT), UDPHandler)
    server.serve_forever()