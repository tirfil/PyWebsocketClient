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

import re
import string
import base64
import hashlib
import struct
import random

import kvheaders

"""
                     -------------------
    dataRecv() ---->|                   |<----- status()
    state() ------->|                   |<----- result()
                    |                   |<----- sendData()
                    |                   |<----- sendHandshake()
                     -------------------
"""

# dataRecv() : data received from network (handshake response or data frame)
# status() : what to do with processing result (i.e send to network, send to application ...)
# result() : processing result
# dataSend() : data to be encoded before sent to network
# state() : state of connection (readyState see websocket API)
# sendPing()
# sendClose()
# sendHandshake()
# setExtensions(): Add extra headers for handshake request

# readyState
#CONNECTING = 0
#OPEN = 1
#CLOSING = 2
#CLOSED = 3

# status
#   0   Nothing to do
#   1   Handshake response OK - Nothing to do
#   2   Handshake response not OK - Nothing to do
#   3   Data (frame encoded) to network
#   4   Pong (After receiving a Ping) to network
#   5   Close (After receiving close) to network
#   6   Send HandShake request to network
#   8   Data (frame decoded) to application

rx_http = re.compile("^HTTP[^ ]* ([^ ]*)")
rx_kv = re.compile("^([^:]*): (.*)")
guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
hsRequest = [ "GET / HTTP/1.1", "Upgrade: websocket", "Connection: Upgrade", "Sec-WebSocket-Version: 13" ]

def hexdump( chars, sep, width ):
    while chars:
        line = chars[:width]
        chars = chars[width:]
        line = line.ljust( width, '\000' )
        print("%s%s%s" % ( sep.join( "%02x" % ord(c) for c in line ),sep, quotechars( line )))
def quotechars( chars ):
    return ''.join( ['.', c][c.isalnum()] for c in chars )

class wsclient:
    def __init__(self):
        self.readyState = 0
        self._status=0
        self._result = ""
        self.ext = {}
        self.key = ""
        self.hsHeaders = kvheaders.kvheaders()
        self.extra=""
        
    def state(self):
        return self.readyState
        
    def status(self):
        return self._status
        
    def dataRecv(self,buffer):
        if self.readyState == 0:
            self.processHandshakeResponse(buffer)
        elif self.readyState > 0:
            self.processData(buffer)
            
    def result(self):
        result = self._result
        self._result = ""
        self._status=0
        return result
        
    def setExtensions(self,ext):
        # Host: Origin: Sec-WebSocket-Protocol:
        self.ext = ext
            
    def sendHandshake(self):
        isKey = False
        request = hsRequest[:]
        for item in self.ext.keys():
            # For test purpose : forcing key
            if string.find(item.lower(),"sec-websocket-key") == 0:
                isKey = True
                self.key = self.ext[item]
            header = "%s: %s" % (item,self.ext[item])
            request.append(header)
        # Sec-WebSocket-Key:
        if not isKey:
            word16=""
            for i in range(16):
                word16 += struct.pack("B",random.uniform(0,255))
            self.key = base64.b64encode(word16)
            header = "Sec-WebSocket-Key: %s" % self.key
            request.append(header)
        request.append("")
        request.append("")
        self._result = "\r\n".join(request)
        print self._result
        self._status = 6
        
    def checkHsHeader(self,key,value):
        if value == "":
            if not self.hsHeaders.hasKey(key):
                print "key error: %s" % key
                return False
        elif not self.hsHeaders.check(key,value):
            print "error: %s: %s" % (key,value)
            return False
        return True
        
    def processHandshakeResponse(self,buffer):
        # HTTP/1.1 101 Switching Protocols
        error = False
        print "handshake response:\n%s" % buffer
        print "-----------------------"
        lines=string.split(buffer,"\r\n")
        start = True
        for line in lines:
            if start:
                start = False
                md = rx_http.search(lines[0])
                if not md:
                    error = True
                else:
                    code = md.group(1)
                    if code != "101":
                        print "http code is %s" % code
                        error = True
                if error == True:
                    print lines[0]
                    break
            else:
                if len(line):
                    md = rx_kv.search(line)
                    if md:
                        key = string.strip(md.group(1))
                        value = string.strip(md.group(2))
                        self.hsHeaders.add(key,value)
                        #print "adding %s: %s" % (key,value)
        if not error:
            if not self.checkHsHeader("upgrade","websocket"):
                error = True
            if not self.checkHsHeader("connection","upgrade"):
                error = True
                
        #TODO; check Sec-WebSocket-Protocol ?
                
        if not error:
            if self.hsHeaders.hasKey("sec-websocket-accept"):
                accept = self.hsHeaders.get("sec-websocket-accept")
                str = "%s%s" % (self.key,guid)
                computed = base64.b64encode(hashlib.sha1(str).digest())
                if accept != computed:
                    print "sec-websocket-accept is %s" % accept
                    print "computed %s" % computed
                    error = True
            else:
                print "missing sec-websocket-accept"
                error = True
        
        if not error:
            self._status = 1
            self.readyState = 1
        else:
            self._status = 2
            self.readyState = 0
            
    def isIncomplete(self):
        if len(self.extra) > 0:
            return True
        else:
            return False
            
    def processData(self,buffer):
        print "processData"

        if len(self.extra)>0:
            buffer = self.extra+buffer
            self.extra=""
        blen = len(buffer)
            
        frame = struct.unpack("BB",buffer[:2])
        if frame[0] > 0x7f:
            final = True
        else:
            final = False
        opcode = frame[0] & 0x0f
        print "Opcode 0x%02x" % opcode
        
        if not opcode in [0x0,0x1,0x2,0x8,0x9,0xa]:
            print "frame error:"
            hexadump(buffer,' ',16)
            self._status=0
            return
            
        if opcode > 0x7:
            control = True
        else:
            control = False
        if frame[1] > 0x7f:
            maskb = True
        else:
            maskb = False
        length = frame[1] & 0x7f
        offset = 2
        if length == 126:
            (length,) = struct.unpack(">H",buffer[2:4])
            offset = 4
        if length == 127:
            (length,) = struct.unpack(">Q",buffer[2:10])
            offset = 10
        print "len= %d" % length
        if maskb:
            masks = struct.unpack("BBBB",buffer[offset:offset+4])
            print "Mask0 0x%02x" % masks[0]
            print "Mask1 0x%02x" % masks[1]
            print "Mask2 0x%02x" % masks[2]
            print "Mask3 0x%02x" % masks[3]
            offset = offset+4
            imask = 0
        last = offset+length
        
        print "frame size: %s, packet size: %s" % (last,blen) 
        if last > blen:
            # packet too small
            self.extra=buffer
            self._status=0
            return

        result = ""
        if maskb:
            for index in range(offset,last):
                (byte,) = struct.unpack("B",buffer[index])
                result += str(unichr(int(byte ^ masks[imask])).encode('utf-8'))
                imask = (imask + 1) % 4
        else:
            result += buffer[offset:last]
        if control:
            # close
            if opcode == 0x8:
                print "Receive Close"
                if self.readyState == 1:
                    self.readyState = 2
                    print "Send Close"
                    self.sendData(result,0x8)
                    self._status = 5
                elif self.readyState == 2:
                    self.readyState = 3
                    self._status = 0
            # ping
            elif opcode == 0x9:
                print "Ping"
                self.sendData(result,0xa)
                self._status = 4
        else:
            # text
            #if opcode == 0x1:
            self._result = result
            self._status=8

        if last < blen:
            # packet too big
            self.extra=buffer[last+1:]
    
    # sendData: note that for client default mask=True
    def sendData(self,buffer,opcode=0x01,final=True,mask=True):
        if mask:
            buffer = buffer.decode('utf8')
        size = len(buffer)
        if final:
            b0=0x80
        else:
            b0=0x00
        b0 += opcode
        if size < 126:
            b1 = size
            if mask:
                b1 |= 0x80
            result = struct.pack(">BB",b0,b1)
        elif size < 65536:
            b1 = 126
            if mask:
                b1 |= 0x80
            result = struct.pack(">BBH",b0,b1,size)
        else:
            b1 = 127
            if mask:
                b1 |= 0x80
            result = struct.pack(">BBQ",b0,b1,size)
        if mask:
            masks=[]
            for i in range(4):
                code = int(random.uniform(0,255))
                print "Mask%d 0x%02x" % (i,code)
                masks.append(code)
            result += struct.pack("BBBB",masks[0],masks[1],masks[2],masks[3])
            imask = 0
            for index in range(size):
                ascii = ord(buffer[index]) ^ masks[imask]
                result += struct.pack("B",ascii)
                imask = (imask + 1) % 4
        else:
            result += buffer
        self._result=result
        self._status=3
        
    def sendPing(self,buffer):
        size = len(buffer)
        if size < 126:
            self.sendData(buffer,0x9)
        else:
            print "Ping data too big"
            self._status=0
            
    def sendClose(self,buffer):
        size = len(buffer)
        if size < 126:
            if self.readyState == 1:
                self.sendData(buffer,0x8)
                self.readyState = 2
            else:
                print "Close wrong state"
        else:
            print "Close data too big"
            self._status=0
              
            
        
if __name__ == "__main__":
    hsResponse = [ "HTTP/1.1 101 Switching Protocols","Upgrade: Websocket", "Connection: Upgrade",
        "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" ]
    buffer = "\r\n".join(hsResponse)
    r = wsclient()
    ext = {}
    ext["Sec-WebSocket-Key"] = "dGhlIHNhbXBsZSBub25jZQ=="
    ext["Host"] = "sip//ws.example.com"
    ext["Origin"] = "http://www.example.com"
    ext["Sec-WebSocket-Protocol"] = "sip"
    r.setExtensions(ext)
    r.sendHandshake()
    if r.status() == 6:
        r.dataRecv(buffer)
        print r.status()

        