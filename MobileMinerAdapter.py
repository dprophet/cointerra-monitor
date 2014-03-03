# Standard BSD license, blah blah, with 1 modification below

# Copyright (c) 2014, Erik Andeson  eanders@pobox.com
# All rights reserved.
# https://github.com/dprophet/cointerra-monitor
# TIPS are appreciated.  None of us can afford to have these machines down:
#  BTC: 12VqRL4qPJ6Gs5V35giHZmbgbHfLxZtYyA
#  LTC: LdQMsSAbEwjGZxMYyAqQeqoQr2otPhJ5Gx

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This module uploads Cointerra stats to MobileMiner by Nate Woolls.  He deserves a lot of credit.  Great App

import os
import time
import datetime
import json
import logging
import urllib
import urllib2
import traceback

class MobileMinerAdapter:

    def __init__(self, logger, sAppKey, sMachineName, sEmailAddress, nTimeout=12):
        self.logger = logger
        self.sApiKey = 'eqezq3oOb9fWhD'  # This is static for this particular cointerra-monitor application.  Dont change it
        self.sAppKey = sAppKey
        self.sMachineName = sMachineName
        self.sEmail = sEmailAddress
        self.OutData = []
        self.timeout = nTimeout

    def SetMachineName (self, sMachineName):
        self.sMachineName = sMachineName

    def SetAppKey (self, sAppKey):
        self.sAppKey = sAppKey

    def SetEmailAddress (self, sEmailAddress):
        self.sEmail = sEmailAddress

    def ClearData (self):
        self.OutData = []

    def addDevices (self, oInStatsStructure):

        for iCount in range(oInStatsStructure['stats']['stats_count']):
            oStat = oInStatsStructure['stats']['stats_array'][iCount]
            sStatId = oStat['id']

            if oStat['type'] == 'asic':

                oAsicMatch = None
                for iCount2 in range(oInStatsStructure['asics']['asic_count']):
                    oAsic = oInStatsStructure['asics']['asics_array'][iCount]
                    sAsicID = oAsic['name'] + str(oAsic['id'])
                    if sAsicID == sStatId:
                        oAsicMatch = oAsic
                        break;

                if oAsicMatch == None:
                    raise RuntimeError("Could not find matching Asic for stat id=" + sStatId)


                device = dict()
                device[u'MinerName'] = 'CointerraMonitor'
                device[u'CoinSymbol'] = 'BTC'
                device[u'CoinName'] = 'Bitcoin'
                device[u'Algorithm'] = 'SHA-256'
                device[u'Name'] = sStatId
                device[u'Kind'] = sStatId
                device[u'HardwareErrorsPercent'] = oAsicMatch['reject_percent']
                device[u'HardwareErrors'] = oStat['hw_errors']
                device[u'PumpRPM'] = oStat['pump_rpm']
                device[u'Status'] = oAsicMatch['status']
                if oAsicMatch[u'enabled'] == u'Y':
                    device[u'Enabled'] = True
                else:
                    device[u'Enabled'] = False
                device[u'AverageHashrate'] = oAsicMatch['hashavg'] * 1000  #Convert to KiloHashes
                device[u'CurrentHashrate'] = oAsicMatch['hash5s'] * 1000
                device[u'Rejected'] = oAsicMatch['rejected']
                device[u'Accepted'] = oAsicMatch['accepted']
                device[u'Temperature'] = oStat['avg_core_temp']
                device[u'AmbientAvgTemp'] = oStat['ambient_avg']
                device[u'Dies'] = oStat['dies']
                device[u'DiesActive'] = oStat['dies_active']
                device[u'LastShareTime'] = oAsicMatch['last_share_t']
                device[u'LastValidWork'] = oAsicMatch['last_valid_t']

                self.OutData.append(device)	


    def SendStats (self):
        sPostURL ='https://mobileminer.azurewebsites.net/api/MiningStatisticsInput?emailAddress='+ self.sEmail + \
            '&applicationKey=' + self.sAppKey + '&machineName=' + self.sMachineName + '&apiKey=' + self.sApiKey

        sJsonData = ""

        try:
            self.logger.info('Sending stats to mobileminer') 
            oRequest = urllib2.Request(sPostURL)
            oRequest.add_header('Content-Type', 'application/json')
            sJsonData = json.dumps(self.OutData)
            response = urllib2.urlopen(oRequest, sJsonData, self.timeout)
            self.logger.info('Successfully sent stats to mobileminer')
        except Exception as e:
            self.logger.error('Error posting stats data to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc())
            print 'Error posting data to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc()


    # This sends a message to the mobile miner application
    def SendMessage (self, sMessage):
        sPostURL ='https://mobileminer.azurewebsites.net/api/NotificationsInput?emailAddress='+ self.sEmail + \
            '&applicationKey=' + self.sAppKey + '&apiKey=' + self.sApiKey

        # oMessage needs to be an array of strings
        oMessage = [sMessage]
        sJsonData = ""

        try: 
            self.logger.info('Sending message to mobileminer')
            oRequest = urllib2.Request(sPostURL)
            oRequest.add_header('Content-Type', 'application/json')
            sJsonData = json.dumps(oMessage)
            response = urllib2.urlopen(oRequest, sJsonData, self.timeout)
            self.logger.info('Successfully SendMessage to mobileminer')
        except Exception as e:
            self.logger.error('Error posting message to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc())
            print 'Error posting data to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc()


    # This sends a message to the mobile miner application
    def GetCommands (self):
        sPostURL ='https://mobileminer.azurewebsites.net/api/RemoteCommands?emailAddress='+ self.sEmail + \
            '&machineName=' + self.sMachineName + '&applicationKey=' + self.sAppKey + '&apiKey=' + self.sApiKey

        try: 
            self.logger.info('Requesting commands from mobileminer')
            oRequest = urllib2.Request(sPostURL)
            response = urllib2.urlopen(oRequest, None, 10)
            sResponse = response.read()
            decoded = json.loads(sResponse.replace('\x00', ''))
            if len(decoded) > 0:
                self.logger.info('Got messages from MobileMiner site.   sResponse=' + sResponse + ', len=' + str(len(sResponse)))
                print 'Got messages from MobileMiner site.   sResponse=' + sResponse + ', len=' + str(len(sResponse))
            return decoded
        except Exception as e:
            self.logger.error('Error getting commands from MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\n' + traceback.format_exc())
            print 'Error getting commands from MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\n' + traceback.format_exc()
            return None

    # This sends a message to the mobile miner application
    def DeleteCommand (self, nCommandID):
        sPostURL ='https://mobileminer.azurewebsites.net/api/RemoteCommands?emailAddress='+ self.sEmail + \
            '&machineName=' + self.sMachineName + '&applicationKey=' + self.sAppKey + '&commandId=' + str(nCommandID) + '&apiKey=' + self.sApiKey

        try: 
            self.logger.info('Requesting commands from mobileminer')
            oRequest = urllib2.Request(sPostURL)
            oRequest.get_method = lambda: 'DELETE'   # creates the delete method
            response = urllib2.urlopen(oRequest, None, 10)
            sResponse = response.read()
            if len(sResponse) > 0:
                print 'sResponse from delete =' + sResponse
                decoded = json.loads(sResponse.replace('\x00', ''))
                if len(decoded) > 0:
                    self.logger.info('Got delete command(' + str(nCommandID) + ') from MobileMiner site.   sResponse=' + \
                                     sResponse + ', len=' + str(len(sResponse)))
                    print 'Got delete command from MobileMiner site.   sResponse=' + sResponse + ', len=' + str(len(sResponse))
            return None
        except Exception as e:
            self.logger.error('Error delete command from MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\n' + traceback.format_exc())
            print 'Error delete command from MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\n' + traceback.format_exc()
            return None

