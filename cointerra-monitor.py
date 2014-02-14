# Standard BSD license, blah blah, with 1 modification (#5)

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

# However!!!! If this doesnt catch a failure case of yours please email me the
#    cointerra_monitor.log and cgminer.log files so I can modify it to catch
#    your issues too.
# 
# Additional Python Dependencies:
#      paramiko                  - SSH2 protocol library
#      scp                       - scp module for paramiko

# I highly recommend the use of some kinds of miner monitoring agents.  I have yet to see any ASIC/GPU gigs run perfectly.
# Either hardware or software issues ends up shutting down your miner until you realize, OMG the coins stopped!  That
# can be 1-14+ days since you had the last issue.  Complacency kills a miners returns.  Monitoring Agents will keep you
# from always having to check statuses.

import socket
import sys
import time
import copy
import logging

import smtplib
import email
import gzip

import json
import os
import urllib2

#SSH and SCP
import paramiko
import scpclient

#
# Configurations
#

cgminer_host = '192.168.1.150'   # Change this to the IP of your Cointerra
cgminer_port = 4028
cointerra_ssh_user = 'root'
cointerra_ssh_pass = 'cointerra' # If you changed password of your Cointerra
log_name = 'cgminer.log'
cointerra_log_file = '/var/log/' + log_name

# Change the below email settings to match your email
email_smtp_server = 'sasl.smtp.pobox.com:587'
email_login = 'eanders@pobox.com'
email_password = 'k4g8l7RjGzTHsZ9Nd%Wn'
email_from = 'eanders@pobox.com'
email_to = 'eanders@pobox.com'

#email_smtp_server = 'smtp.gmail.com:587'
#email_login = 'mylogin'
#email_password = 'mypassword'
#email_from = 'myemail@example.com'
#email_to = 'myemail@example.com'

#all emails from this script will start with this
email_subject_prefix = 'Cointerra Watcher'

email_warning_subject = 'Warning'  #subject of emails containing warnings (Like temperature)
email_error_subject = 'Error'      #subject of emails for errors (these are serious and require a reboot)

monitor_interval = 60  #interval between checking the cointerra status (in seconds)
monitor_wait_after_email = 60  #waits 60 seconds after the status email was sent
monitor_restart_cointerra_if_sick = True  #should we reboot the cointerra if sick/dead
monitor_send_email_alerts = True  #should emails be sent containing status information, etc.

max_temperature = 85.0  #maximum rate temperature before a warning is sent in Celcius
cointerra_min_mhs_sha256 = 1500000  #minimum expected hash rate for sha256, if under, warning is sent in MH/s

n_devices = 0  #Total nunber of ASIC processors onboard.  We will query for the count.
n_error_counter = 0
n_max_error_count = 3  # How many errors before you reboot the cointerra
n_reboot_wait_time = 60  #How many seconds after the the reboot of the cointerra before we restart the loop
n_hardware_reboot_percentage = 5  #If the hardware error percentage is over this value we will reboot.  -1 to disable

sLogFilePath = os.getcwd()  # Directory where you want this script to store the Cointerra log files in event of troubles

bDebug = False

# Possible logging levels are
#  logging.INFO  This is a lot of logs.  You will likely need this level of logging for support issues
#  logging.INFO
nLoggingLevel = logging.INFO

n_ambient_temperature = 0

oStatsStructure = {}

#
# Configurations
#

#
# For checking the internet connection
#

def internet_on():
    try:
        response = urllib2.urlopen('http://www.google.com/', timeout = 10)
        return True
    except urllib2.URLError as err: pass
    
    return False

#
# cgminer RPC
#

class CgminerClient:
    def __init__(self, host, port):
        self.host = host
        self.rpc_port = port

    def command(self, command, parameter):
        # sockets are one time use. open one for each command
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        received = {}
        received['message'] = None
        received['error'] = None

        try:
            mycommand = ""
            if parameter:
                mycommand = json.dumps({"command": command, "parameter": parameter})
            else:
                mycommand = json.dumps({"command": command})

            if bDebug:
                print 'host ' + self.host + ' port:' + str(self.rpc_port) + ', command:' + mycommand

            self.logger.info('host ' + self.host + ' port:' + str(self.rpc_port) + ', command:' + mycommand)

            sock.connect((self.host, self.rpc_port))
            self._send(sock, mycommand)
            received['message'] = self._receive(sock)
        except Exception as e:
            print 'Got a socket Error.  Error = below'
            received['error'] = 'SOCKET_ERROR: ' + str(e)
            print received['error']
            self.logger.error(received['error'])
            sock.close()
            return received

        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except:
            pass # restart makes it fail, but it's ok

        # the null byte makes json decoding unhappy
        try:
            decoded = json.loads(received['message'].replace('\x00', ''))
            myprettyjson = json.dumps(decoded, sort_keys=True, indent=4)
            if bDebug:
                print 'Received ' + myprettyjson

            self.logger.info(myprettyjson)
            received['message'] = decoded
            return received
        except:
            pass # restart makes it fail, but it's ok

    def _send(self, sock, msg):
        totalsent = 0
        while totalsent < len(msg):
            sent = sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def _receive(self, sock, size=65500):
        msg = ''
        while True:
            chunk = sock.recv(size)
            if chunk == '':
                # end of message
                break
            msg = msg + chunk
        return msg

    def setLogger (self, logger):
        self.logger = logger




class JSONMessageProcessor:
    def __init__(self, logger):
        self.logger = logger


    def AscicCountBlock(self, sStatsObject, sAscicCountJSON):
        
        self.logger.info('Processing ascic count block')

        sStatsObject['asics'] = {}

        sStatsObject['asics']['asic_count'] = sAscicCountJSON['ASCS'][0]['Count']

        return sStatsObject


    def CoinBlock(self, sStatsObject, sCoinJSON):

        self.logger.info('Processing coin block')

        sStatsObject['coin'] = sCoinJSON['COIN'][0]['Hash Method']

        return sStatsObject


    def PoolBlock(self, sStatsObject, sPoolJSON):
        self.logger.info('Processing pool block')

        sStatsObject['pools'] = {}
        sStatsObject['pools']['pools_array'] = []

        sStatsObject['pools']['pool_count'] = len(sPoolJSON['POOLS'])

        for iPool in range(sStatsObject['pools']['pool_count']):
            poolurl = sPoolJSON['POOLS'][iPool]['Stratum URL']
            poolstatus = sPoolJSON['POOLS'][iPool]['Status']
            poolAccepted = sPoolJSON['POOLS'][iPool]['Accepted']
            poolRejected = sPoolJSON['POOLS'][iPool]['Rejected']
            poolWorks = sPoolJSON['POOLS'][iPool]['Works']
            poolNumber = sPoolJSON['POOLS'][iPool]['POOL']
            poolDiscarded = sPoolJSON['POOLS'][iPool]['Discarded']
            poolPriority = sPoolJSON['POOLS'][iPool]['Priority']
            poolQuota = sPoolJSON['POOLS'][iPool]['Quota']
            poolWorks = sPoolJSON['POOLS'][iPool]['Works']
            poolGetFailures = sPoolJSON['POOLS'][iPool]['Get Failures']
            iTime = sPoolJSON['POOLS'][iPool]['Last Share Time']
            poolLastShareTime = time.strftime('%m/%d/%Y %H:%M:%S', time.localtime(iTime))

            sStatsObject['pools']['pools_array'].insert(poolNumber, dict([('URL', poolurl), ('status', poolstatus), ('accepted', poolAccepted), \
                                                                          ('rejected', poolRejected), ('works', poolWorks), \
                                                                          ('discarded', poolDiscarded), ('quota', poolQuota), \
                                                                          ('priority', poolPriority), ('works', poolWorks), \
                                                                          ('get_failures', poolGetFailures), ('last_share_time', poolGetFailures), \
                                                                          ('last_share_time', poolLastShareTime)]))

        return sStatsObject



    def StatsBlock(self, sStatsObject, sStatsJSON):
        self.logger.info('Processing stats block')

        sStatsObject['stats'] = {}
        iLen = len(sStatsJSON['STATS'])
        sStatsObject['stats']['stats_count'] = iLen
        sStatsObject['stats']['stats_array'] = []

        for iStat in range(iLen):
            result = sStatsJSON['STATS'][iStat]
            thisStat = {}
            thisStat['id'] = result['ID']
            thisStat['stat_number'] = result['STATS']

            if result['ID'].startswith('CTA'):
                # this is a ASIC stat
                thisStat['avg_core_temp'] = 0
                thisStat['hw_errors'] = 0
                thisStat['type'] = 'asic'
                thisStat['board_num'] = result['Board number']
                thisStat['calc_hashrate'] = result['Calc hashrate']
                thisStat['ambient_avg'] = result['Ambient Avg']
                thisStat['asics'] = result['Asics']
                thisStat['board_num'] = result['Board number']
                thisStat['dies'] = result['Dies']
                thisStat['dies_active'] = result['DiesActive']
                thisStat['active'] = result['Active']
                thisStat['inactive'] = result['Inactive']
                thisStat['cores'] = result['Cores']
                thisStat['underruns'] = result['Underruns']
                thisStat['serial'] = result['Serial']
                thisStat['elapsed'] = result['Elapsed']
                thisStat['uptime'] = result['Uptime']
                thisStat['raw_hashrate'] = result['Raw hashrate']
                thisStat['rejected_hashrate'] = result['Rejected hashrate']
                thisStat['total_hashes'] = result['Total hashes']
                thisStat['pump_rpm'] = result['PumpRPM0']
                thisStat['fm_date'] = result['FW Date']
                thisStat['fm_revision'] = result['FW Revision']

                # Calculate the average core temperature and hardware errors
                for iDies in range(thisStat['dies']):
                    sKey = 'CoreTemp' + str(iDies)
                    thisStat['avg_core_temp'] = thisStat['avg_core_temp'] + result[sKey]

                    sKey = 'HWErrors' + str(iDies)

                    thisStat['hw_errors'] = thisStat['hw_errors'] + result[sKey] / 100

                thisStat['avg_core_temp'] = float(thisStat['avg_core_temp']) / float(100) / float(thisStat['dies'])

                iId = 0
                sKey = 'FanRPM' + str(iId)
                myval = result.get(sKey)

                while myval != None:
                    if thisStat.get('fans') == None:
                        thisStat['fans'] = {}
                        thisStat['fans']['fan_count'] = 0

                    thisStat['fans']['fan_count'] = thisStat['fans']['fan_count'] + 1
                    thisStat['fans'][sKey] = myval

                    iId = iId + 1
                    sKey = 'FanRPM' + str(iId)
                    myval = result.get(sKey)

            else:
                thisStat['type'] = 'pool'
                thisStat['bytes_recv'] = result['Bytes Recv']
                thisStat['bytes_recv'] = result['Bytes Sent']
                thisStat['work_difficulty'] = result['Work Diff']


            sStatsObject['stats']['stats_array'].insert(iStat, thisStat)



        return sStatsObject

    # Process the ASIC RPC message
    def AscicBlock(self, sStatsObject, nAsicNumber, sAscicJSON):
        self.logger.info('Processing ascic block')

        if sStatsObject['asics'].get('asics_array') == None:
            sStatsObject['asics']['asics_array'] = []

        result = sAscicJSON['ASC'][0]

        asicStatus = result['Status']  #If this is ever bad, not good!!!
        asicName = result['Name']
        asicHash5s = result['MHS 5s']
        asicHashAvg = result['MHS av']
        asicHardwareErrors = result['Hardware Errors']
        asicRejected = result['Rejected']
        asicAccepted = result['Accepted']
        asicID = result['ID']
        asicEnabled = result['Enabled']
        asicDeviceRejectPercent = result['Device Rejected%']

        sStatsObject['asics']['asics_array'].insert(nAsicNumber, dict([('status', asicStatus), ('name', asicName), ('hash5s', asicHash5s), \
                                                                       ('hashavg', asicHashAvg), ('hw_errors', asicHardwareErrors), \
                                                                       ('rejected', asicRejected), ('id', asicID), ('enabled', asicEnabled), \
                                                                       ('accepted', asicAccepted), ('reject_percent', asicDeviceRejectPercent)]))
        
        return sStatsObject

    # Processes the summary JSON return from a summary command
    def SummaryBlock(self, sStatsObject, sSummaryJSON):
        self.logger.info('Processing ascic block')

        result = sSummaryJSON['SUMMARY'][0]

        sStatsObject['summary'] = {}
        sStatsObject['summary']['hw_errors'] = result['Hardware Errors']
        sStatsObject['summary']['hash5s'] = result['MHS 5s']
        sStatsObject['summary']['hashavg'] = result['MHS av']
        sStatsObject['summary']['pool_reject_percent'] = result['Pool Rejected%']
        sStatsObject['summary']['pool_stale_percent'] = result['Pool Stale%']
        sStatsObject['summary']['blocks_found'] = result['Found Blocks']    # Lucky?  Should have solo mined
        sStatsObject['summary']['discarded'] = result['Discarded']
        sStatsObject['summary']['rejected'] = result['Rejected']
        sStatsObject['summary']['get_failures'] = result['Get Failures']
        sStatsObject['summary']['get_works'] = result['Getworks']

        return sStatsObject



class CointerraSSH:
    def __init__(self, host, port, user, passwd, sLogFilePath, logger):
        self.host = host
        self.ssh_port = port
        self.user = user
        self.password = passwd
        self.sLogFilePath = sLogFilePath
        self.logger = logger

    # Creates an SSH connection
    def createSSHClient(self):
        self.logger.info('createSSHClient host ' + self.host + ' port:' + str(self.ssh_port))

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.host, self.ssh_port, self.user, self.password)
        return client

    # Creates an SCP file transfer client
    def CreateScpClient(self):
        ssh_client = self.createSSHClient()
        scp = SCPClient(ssh_client)

    def reboot(self):

        try:
            self.logger.error('Rebooting the cointerra')
            print 'Rebooting the cointerra'
            ssh_client = self.createSSHClient()
            transport = ssh_client.get_transport()
            session = transport.open_session()
            session.exec_command('/sbin/reboot')
            if session.recv_ready():
                data = session.recv(4096)
                print 'Reboot results =' + data

            time.sleep(5)
            ssh_client.close()
            print 'Cointerra has been rebooted'
            self.logger.error('Cointerra has been rebooted')

        except Exception as e:
            print e
            ssh_client.close()


    # Executes a ps command on the cointerra looking for the cgminer program
    def isCGMinerRunning(self):
        bReturn = False

        try:
            ssh_client = self.createSSHClient()

            transport = ssh_client.get_transport()
            session = transport.open_session()
            session.exec_command('ps -deaf | grep cgminer')
            if session.recv_ready():
                data = session.recv(4096)

                nIndex = data.find('/opt/cgminer')

                if bDebug:
                    print 'received over SSH =' + data
                    print 'Index for /opt/cgwatcher =' + str(nIndex)

                if nIndex > 0:
                    bReturn = True
            else:
                print 'This should happen. session.recv_ready() isnt ready'

            ssh_client.close()

        except Exception as e:
            print 'Error thrown in isCGMinerRunning ='
            print e
            ssh_client.close()

        return bReturn

    def ScpLogFile(self, sFileName):

        try:

            if bDebug:
                print 'SCP file:' + sFileName + ' from host ' + self.host

            ssh_client = self.createSSHClient()
            transport = ssh_client.get_transport()

            myscpclient = scpclient.SCPClient(transport)

            if bDebug:
                print 'SCP file' + sFileName + ' to host:' + self.host

            #this will copy the file from the cointerra to the local PC
            myscpclient.get(sFileName, self.sLogFilePath)

            #compress the log file.  Can be very large for emailing
            spath, sname = os.path.split(sFileName)

            f_in = open(self.sLogFilePath + "/" + sname, 'rb')
            f_out = gzip.open(self.sLogFilePath + "/" + sname + '.gz', 'wb')
            f_out.writelines(f_in)
            f_out.close()
            f_in.close()

            os.remove(self.sLogFilePath + "/" + sname)

        except Exception as e:
            print 'Error thrown in ScpLogFile ='
            print e
            ssh_client.close()





#
# Utils
#

def SendEmail(from_addr, to_addr_list, cc_addr_list,
              subject, message, login, password,
              smtpserver = email_smtp_server,
              sLogfile = None):

    if sLogfile == None:
        header = 'From: %s\n' % from_addr
        header += 'To: %s\n' % ','.join(to_addr_list)
        header += 'Cc: %s\n' % ','.join(cc_addr_list)
        header += 'Subject: %s\n\n' % (email_subject_prefix + '_' + subject)

        server = smtplib.SMTP(smtpserver)
        server.starttls()
        server.login(login, password)
        server.sendmail(from_addr, to_addr_list, header + message)
        server.quit()
    else:

        msg = email.MIMEMultipart.MIMEMultipart()
        msg['Subject'] = email_subject_prefix + '_' + subject 
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addr_list)

        msg.attach(email.MIMEText.MIMEText(message))

        part = email.MIMEBase.MIMEBase('application', "octet-stream")
        part.set_payload(open(sLogfile, "rb").read())
        email.Encoders.encode_base64(part)

        part.add_header('Content-Disposition', 'attachment; filename="cointerra.log.gz"')

        msg.attach(part)

        server = smtplib.SMTP(smtpserver)
        server.starttls()
        server.login(login, password)
        server.sendmail(from_addr, to_addr_list, msg.as_string())
        server.quit()


# This is the main execution module
def StartMonitor(client):
    os.system('clear')

    #time internet was lost and reconnected
    internet_lost = 0
    internet_reconnected = 0
    bError = False
    global n_error_counter
    global n_devices
    global n_ambient_temperature
    global oStatsStructure
    global n_hardware_reboot_percentage
    global n_max_error_count
    sLastGoodJSONEntry = ''

    # Delete the old log file
    if os.path.isfile(sLogFilePath + '/cointerra_monitor.log') == True:
        os.remove(sLogFilePath + '/cointerra_monitor.log')

    logger = logging.getLogger('myapp')
    hdlr = logging.FileHandler(sLogFilePath + '/cointerra_monitor.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(nLoggingLevel)
    client.setLogger(logger)

    logger.error('Starting cointerra-watcher ' + time.strftime('%m/%d/%Y %H:%M:%S'))

    test_internet_connection = False

    last_command_check = time.time()
    last_internet_check = time.time()
    last_internet_check_email_sent = time.time()

    cointerraSSH = CointerraSSH(cgminer_host, 22, cointerra_ssh_user, cointerra_ssh_pass, sLogFilePath, logger)
    messageProcessor = JSONMessageProcessor(logger)
    cointerraSSH.isCGMinerRunning()
    
    while(1):
        output = ''
        bError = False
        bWarning = False
        bSocketError = False
        oStatsStructure = {}

        must_send_email = False
        must_restart = False

        oStatsStructure['time'] = time.strftime('%m/%d/%Y %H:%M:%S')
        # get the count of the number of ASIC units in the cointerra
        result = client.command('asccount', None)
        if result['message']:
            messageProcessor.AscicCountBlock(oStatsStructure,result['message'])
            n_devices = oStatsStructure['asics']['asic_count']

            for loop in range(n_devices):
                result = client.command('asc', str(loop))
                if result:
                    messageProcessor.AscicBlock(oStatsStructure, loop, result['message'])

        else:
            output = output + result['error']
            bSocketError = True


        result = client.command('coin', None)
        if result['message']:
            messageProcessor.CoinBlock(oStatsStructure,result['message'])
        else:
            output = output + result['error']
            bSocketError = True


        result = client.command('pools', None)
        if result['message']:
            messageProcessor.PoolBlock(oStatsStructure,result['message'])
        else:
            output = output + result['error']
            bSocketError = True
 
        result = client.command('summary', None)
        if result['message']:
            messageProcessor.SummaryBlock(oStatsStructure, result['message'])
        else:
            output = output + result['error']
            bSocketError = True

        result = client.command('stats', None)
        if result['message']:
            messageProcessor.StatsBlock(oStatsStructure, result['message'])
        else:
            output = output + result['error']
            bSocketError = True

        # Make it more human readable
        sPrettyJSON = json.dumps(oStatsStructure, sort_keys=False, indent=4)

        if bDebug:
            print 'new oStatsStructure = ' + sPrettyJSON

        logger.info('new oStatsStructure = ' + sPrettyJSON)

        if bSocketError == False:
            # The oStatsStructure contains all of the cointerra stats from calls to the cgminer RPC port
            for iCount in range(oStatsStructure['asics']['asic_count']):
                if oStatsStructure['asics']['asics_array'][iCount]['status'] != 'Alive':
                    n_error_counter = n_error_counter + 1
                    output = 'Asic #' + str(iAsic) + ' bad status =' + oStatsStructure['asics']['asics_array'][iCount]['status']
                    bError = True
                    break
                elif oStatsStructure['asics']['asics_array'][iCount]['reject_percent'] > n_hardware_reboot_percentage:
                    n_error_counter = n_error_counter + 1
                    output = 'Asic #' + str(iAsic) + ' Hardware Errors too high ' + str(oStatsStructure['asics']['asics_array'][iCount]['reject_percent'])
                    bError = True
                    break
        else:
            n_error_counter = n_error_counter + 1

        if (bError == True) or (bSocketError == True):
            if n_error_counter > n_max_error_count:
                sJsonContents = ''  # Reference to which JSON contents

                # If a socket error use the last known good JSON contents
                if bSocketError == True:
                    sJsonContents = sLastGoodJSONEntry
                else:
                    sJsonContents = sPrettyJSON

                print oStatsStructure['time'] + output
                print 'Rebooting machine and sending email.  Will sleep for ' + str(n_reboot_wait_time) + ' seconds'
                print sJsonContents

                logger.error('Rebooting machine and sending email.  Will sleep for ' + str(n_reboot_wait_time) + ' seconds')
                logger.error(sJsonContents)

                cointerraSSH.ScpLogFile(cointerra_log_file)

                if monitor_restart_cointerra_if_sick == True:
                    cointerraSSH.reboot()

                if monitor_send_email_alerts:
                    SendEmail(from_addr = email_from, to_addr_list = [email_to], cc_addr_list = [],
                              subject = email_error_subject,
                              message = output + '\n' + sJsonContents,
                              login = email_login,
                              password = email_password,
                              sLogfile = sLogFilePath + '/' + log_name + '.gz')

                os.remove(sLogFilePath + '/' + log_name + '.gz')
                time.sleep(n_reboot_wait_time)

                n_error_counter = 0  # Reset the error counter
        elif bWarning == True:
            if monitor_send_email_alerts:

                sJsonContents = sPrettyJSON

                print oStatsStructure['time'] + output
                print 'System warning '
                print sJsonContents

                logger.error('System warning: ' + output)
                logger.warning(sJsonContents)

                SendEmail(from_addr = email_from, to_addr_list = [email_to], cc_addr_list = [],
                          subject = email_warning_subject,
                          message = output + '\n' + sJsonContents,
                          login = email_login,
                          password = email_password,
                          sLogfile = sLogFilePath + '/' + log_name + '.gz')
        else:
            print oStatsStructure['time'] + ' everything is alive and well'
            logger.warn(oStatsStructure['time'] + ' everything is alive and well')
            sLastGoodJSONEntry = copy.deepcopy(sPrettyJSON)

        # Sleep by increments of 1 second to catch the keyboard interrupt
        for i in range(monitor_interval):
            time.sleep(1)

        if bDebug:
            os.system('clear')

    return

# """
# Usage: cgminer-monitor.py [command] [parameter]
#
# Script will need to open a socket, so running in super-user mode may be needed
#
# No arguments: monitor + http server mode. Press CTRL+C to stop.
# Arguments: send the command with optional parameter and exit.
#

# Useful error translations:
# [Errno 111] Connection refused - cgminer's API has not been started yet
#       Solution: Be sure to run cgminer with '--api-listen --api-allow W:127.0.0.1'
#
# [Errno 107] Transport endpoint is not connected
#       Solution: Check that the --api-allow address is correct
#
# [Errno -2] Name or service not known
#       Solution: Make sure your imap and smtp server locaions are correct
#                     The script may crash if there is a port on the imap server, leave it without a port


if __name__ == "__main__":

    command = sys.argv[1] if len(sys.argv) > 1 else None
    parameter = sys.argv[2] if len(sys.argv) > 2 else None

    client = CgminerClient(cgminer_host, cgminer_port)

    if command:
        # An argument was specified, ask cgminer and exit
        result = client.command(command, parameter)
        print str(result) if result else 'Cannot get valid response from cgminer'
        sys.exit(1)
    else:
        # No argument, start the monitor and the http server
        try:

            #start the monitor
            StartMonitor(client)

        except KeyboardInterrupt:
            sys.exit(0)
