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

    def __init__(self, logger, sAppKey, sMachineName, sEmailAddress):
        self.logger = logger
        self.sApiKey = 'eqezq3oOb9fWhD'  # This is static for this particular application
        self.sAppKey = sAppKey
        self.sMachineName = sMachineName
        self.sEmail = sEmailAddress
        self.OutData = []

    def SetMachineName (self, sMachineName):
        self.sMachineName = sMachineName

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
                device[u'RejectPercent'] = oAsicMatch['reject_percent']
                device[u'HardwareErrors'] = oStat['hw_errors']
                device[u'PumpRPM'] = oStat['pump_rpm']
                device[u'Status'] = oAsicMatch['status']
                if oAsicMatch[u'enabled'] == u'Y':
                    device[u'Enabled'] = True
                else:
                    device[u'Enabled'] = False
                device[u'AverageHashrate'] = oAsicMatch['hashavg'] * 1000
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
            oRequest = urllib2.Request(sPostURL)
            oRequest.add_header('Content-Type', 'application/json')
            sJsonData = json.dumps(self.OutData)
            response = urllib2.urlopen(oRequest, sJsonData)
        except Exception as e:
            self.logger.error('Error posting data to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc())
            print 'Error posting data to MultiMiner Exception: ' + str(e) + '\nURL=' + \
                              sPostURL + '\nsJsonData=' + sJsonData + '\n' + traceback.format_exc()

        # clear the buffer so its clean for the next time
        self.OutData = []

