#!/usr/bin/python
# -*- coding: UTF-8 -*-

import time

import http
from kivy.utils import platform
from notification_demo.components.notification import Notification
from threadcomm.threadcomm import ThreadComm, ThreadCommServer


class Service():
    CONFIG_THREADCOMMPORT = 51352
    CONFIG_THREADCOMMID = " sigmawebplus"
    
    #Objects
    threadComm = None
    sigmaWeb = None
    
    #Signals
    SIGTERM = False
    
    #Configuration
    userData = {
                'update_timeout': None,
                'update_auto':    False,
                'update_time':    0,
                'update_data':    None,
                'update_hash':    None
                }
    
    def run(self):
        print "Monitor: Started successfully"
        
        #Start ThreadComm
        self.threadComm = ThreadComm(self.CONFIG_THREADCOMMPORT, self.CONFIG_THREADCOMMID, ThreadCommServer)
        self.threadComm.start()
        
        #Start SigmaWebMonitor
        self.sigmaWeb = SigmaWebMonitor()
        
        #Run until SIGTERM
        while (self.SIGTERM==False):
            #Listen and respond to ThreadComm messages
            self.listen()
            
            #Verifica por novas notas no sistema
            if self.userData['update_auto'] and self.sigmaWeb.enoughInfo(): #Checka se o monitor esta autorizado a verificar notas e o SigmaWebMonitor tem informacoes suficientes
                if (float(self.userData['update_time']) + self.userData['update_timeout']) < time.time():                     
                    self.userData['update_time'] = int(time.time())
                    self.check()
            
            #Wait one second until next cycle (avoid consuming too much processing power)
            time.sleep(1)
        
        #Stop service
        self.threadComm.sendMsg("DIE") #Warn app that the service is closing!
        self.threadComm.stop()
        print "Monitor: Killed successfully"
    
    def kill(self):
        self.SIGTERM = True
    
    def check(self):
        try:
            print "Debug: Fetching data from server..."
            fireNotification, serverResponse = self.sigmaWeb.check()
        except SigmaWebMonitorException as e:
            if str(e)[1:15] == "Server error: ":
                self.threadComm.sendMsg("ERR "+str(e)[15:-1])
            elif str(e)  == "'Data is already up to date'":
                self.threadComm.sendMsg("UTD "+str(self.userData['update_time']))
            elif str(e) == "'Unable to fetch data from server'":
                print "Monitor: Unable to fetch data from server"
            else:
                raise
        else:
            self.threadComm.sendMsg("NNA "+str(self.userData['update_time'])+serverResponse)
            
            if fireNotification:
                Notification("SigmaWeb+","Novas notas disponiveis!").notify()
        
    
    def listen(self):
        #Check for ThreadComm messages
        while True:
            try:
                message = self.threadComm.recvMsg()
            except:
                return False
            
            print message
            if message[:3] == "TOC": #Timeout change
                self.userData['update_timeout'] = float(message[4:]) * 60
            elif message[:3] == "ATC": #Auto check
                self.userData['update_auto'] = (message[4:] == "1")
            elif message[:3] == "CKN": #Check now
                self.userData['update_time'] = 0
            elif message[:3] == "KIL": #Kill
                self.threadComm.sendMsg("KI1 "+str(self.userData['update_time']))
                self.threadComm.sendMsg("KI2 "+self.sigmaWeb.getData())
                self.kill()
            elif message[:3] == "SNT": #Send notification
                Notification("SigmaWeb+",message[4:]).notify()
            elif message[:3] == "UNC": #Username change
                self.sigmaWeb.setUsername(message[4:])  
            elif message[:3] == "UNP": #Password change
                self.sigmaWeb.setPassword(message[4:])
            elif message[:3] == "HSC": #Hash change
                self.sigmaWeb.setHash(message[4:])
            elif message[:3] == "LCK": #Hash change
                if message[4:] <> "":
                    self.userData['update_time'] = int(message[4:])
        return True
        
class SigmaWebMonitor:
    username = None
    password = None
    hash = None
    data = None
    
    def check(self):
        if not self.enoughInfo():
            raise SigmaWebMonitorException("Not enough data to fetch information from server")
        
        try:
            pagina = http.Page("http://www.sigmawebplus.com.br/server/")
            pagina.set_RequestHeaders(http.Header("username", self.username), http.Header("password", self.password), http.Header("hash", self.hash))
            pagina.Refresh()
            response = pagina.get_ResponseData()
        except:
            raise SigmaWebMonitorException("Unable to fetch data from server")
        
        #Avalia a resposta
        if response[:7] == "<error>":
            raise SigmaWebMonitorException("Server error: "+response[7:-8])
        elif response[:10] == "Up-to-date":
            raise SigmaWebMonitorException("Data is already up to date")
        
        notification = not (self.hash == "")
        self.hash = response[:32]
        self.data = response
        return notification, response
    
    def enoughInfo(self):
        if (self.username == None) or (self.password==None) or (self.hash==None):
            return False
        else:
            return True
            
    
    def setUsername(self, username):
        if not (username == ""):
            self.username = username
        else:
            self.username = None
    
    def setPassword(self, password):
        if not (password==""):
            self.password = password
        else:
            self.password = None
    
    def setHash(self, hash):
        self.hash = hash
        
    def getData(self):
        if not (self.data == None):
            return self.data
        return ""
        
class SigmaWebMonitorException(Exception):
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)            
        

if __name__ == '__main__':
    #On Android platform this code is executed automaticaly
    Service().run()