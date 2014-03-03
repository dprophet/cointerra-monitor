<pre>
Copyright (c) 2014, Erik Andeson  eanders@pobox.com
All rights reserved.
https://github.com/dprophet/cointerra-monitor
TIPS are appreciated.  None of us can afford to have these machines down:
 BTC: 12VqRL4qPJ6Gs5V35giHZmbgbHfLxZtYyA
 LTC: LdQMsSAbEwjGZxMYyAqQeqoQr2otPhJ5Gx


cointerra-monitor
=================

Monitors the Cointerra Bitcoin Miners for Errors.  Sends emails with the cointerra log
files attached and will reboot the cointerra machine

Remote monitoring agent for the Cointerra Terraminer Bitcoin Mining machines. Monitors
for errors, sends email notifications and log files, full integration with MobileMiner
on IOS/Android/Windows Phone. Remotely reboots Cointerra in event of critical errors.
Supports RESTART command from MobileMiner

To install and run this monitor (See windows instructions below)
1) Download and install Python 2.x. DO NOT USE Python 3.X!!!
   - http://www.python.org/downloads/
2) Install Python Package Index (pip)
   - http://www.pip-installer.org/en/latest/installing.html
3) Use pip and install paramiko
   Example:
   sudo pip install paramiko
4) Install git (the prefered mechanism over downloading source)
   - http://git-scm.com/downloads
   - Open a command shell, cd to the directory you want the code, and run
     git clone https://github.com/dprophet/cointerra-monitor.git
   - Note: For some of you Windows folks that want nice GUI download TortoiseGIT or
     Sourcetree
   - If you want to fetch my latest changes do
     git pull
5) Rename config_sample.json to config.json
6) Edit the config.json file.  Add configurations for all of your Cointerra machines
7) Then just run
   python cointerra-monitor.py
   - If everything is working correctly you will get success messages like
     02/23/2014 07:12:56 MyCointerra1: everything is alive and well
     02/23/2014 07:12:59 MyCointerra2: everything is alive and well
   - If its not running correctly you will get programmer/debugging stack crash messages
8) If all else fails, arrange a time with me, give me a BTC/LTC tip, and we can TeamView
   and I will setup for you.


For Windows 7 install here are the instructions (Contrinuted by Emba)
   http://forum.cointerra.com/threads/cointerra-monitoring-agent-with-email-mobileminer-support.442/#post-2092
1. Install python-2.7.6.amd64.msi (or the 32bit version if required)
   make sure to install it to c:/python27
2. install pycrypto-2.6.win-amd64-py2.7.exe
3. extract monitor final.zip
4. copy all files inside the zip into C:/python27
5. Run ez_setup.bat which will install easy_install
6. run ecdsa.bat
7. open the config.json file with notepad or your chosen text editor and add in your
   mobile miner API key and email and your email address for alerts if required
8. now simply run start.bat and it should start the monitor (there are some errors
   at the start but it seems to run ok)
9. Do steps 4-8 above under "To install and run this monitor"

Each Cointerra machine configuration supports N number of MobileMiners so N number of
people can be notified of issues.  I like to take vacations as much as the next person.

As of 2/22/2014 the algorithm of the monitor is as follows
1)  Read the config.json file
2)  Create a CgminerClient to communicate with the the cgminer's running on the Cointerra
    machines
3)  Create a logger to write out to a log file
4)  Create a JSONMessageProcessor
5)  Create a MobileMinerAdapter (if MobileMiner is configured)
6)  Create a CointerraSSH (Allows us to copy log files from the machine and execute remote
    commands like reboot)
7)  Loop for each Configured Cointerra Machine
      - Execute the asccount RPC call
        - Execute the asic RPC call for each of the ASIC chips
      - Execute the coin RPC call
      - Execute the pools RPC call
      - Execute the summary RPC call
      - Execute the stats RPC call
8)  Parse all the RPC results from above and load to a Python datastructure (oStatsStructure)
9)  If there was no socket communications error with the Cointerra
      - Upload various stats on oStatsStructure to the MobileMiner Web API's.  Send stats
        for every configured MobileMiner
      - Check various stats on the oStatsStructure.  Set error flags and messages
        - If number of dies and active dies are not the same set an error flag
        - If an ASIC status is not 'Alive' the set an error flag
        - If reject_percent > 5% set an error flag
        - If the ASIC chip enabled is not 'Y' set an error flag
      - Check various stats as warnings.  Warnings are the same as errors but warnings will
        not reboot the machine.
        - If avg_core_temp or ambient_avg > max temperature set a warning flag.
        - Loop through the core_temps array and check the temperature of all cores.  If over
          max set a warning flag 
11) Check the error and socketerror flags.  If there were errors
      - Check to see if error count is 3 or over.  If error count less than 3 go back to #7
      - Print error messages to the console and log file
      - Send a message to MobileMiner
      - SCP and GZIP log files from the Cointerra machine: cgminer.log
      - Reboot the cointerra
      - GZIP the cointerra-monitor.log file
      - Create an email.  Attach the GZIP compressed log files
      - Delete the compressed files
      - Sleep for 2 minutes to wait for the Cointerra to come back online
      - Go back to #7
12)  Check for warning flags.  Warning flags are same as #11 above but do not reboot the
     machine.  Currently the only warning flags are temperature
13)  Checks MobileMiner system for remote commands.  Currently I only support RESTART
     which will reboot the cointerra.
14)  Sleep and wait for x period of time based on if machines were rebooted or not
</pre>
