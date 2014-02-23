Copyright (c) 2014, Erik Andeson  eanders@pobox.com
All rights reserved.
https://github.com/dprophet/cointerra-monitor
TIPS are appreciated.  None of us can afford to have these machines down:
 BTC: 12VqRL4qPJ6Gs5V35giHZmbgbHfLxZtYyA
 LTC: LdQMsSAbEwjGZxMYyAqQeqoQr2otPhJ5Gx


cointerra-monitor
=================

Monitors the Cointerra Bitcoin Miners for Errors.  Sends emails with the cointerra log files attached and will reboot the cointerra machine

To install and run this monitor
1) Download and install Python 2.x
2) Install Python Package Index (pip)
3) Use pip and install paramiko
4) Rename config_sample.json to config.json
5) Edit the config.json file.  Add configurations for all of your Cointerra machines
6) Then just run
   python cointerra-monitor.py

Each Cointerra machine configuration supports N number of MobileMiners so N number of people
can be notified of issues.  I like to take vacations as much as the next person.

As of 2/22/2014 the algorithm of the monitor is as follows
1)  Read the config.json file
2)  Create a CgminerClient to communicate with the the cgminer's running on the Cointerra machines
3)  Create a logger to write out to a log file
4)  Create a JSONMessageProcessor
5)  Create a MobileMinerAdapter (if MobileMiner is configured)
6)  Create a CointerraSSH (Allows us to copy log files from the machine and execute remote commands like reboot)
7)  Loop for each Configured Cointerra Machine
      - Execute the asccount RPC call
        - Execute the asic RPC call for each of the ASIC chips
      - Execute the coin RPC call
      - Execute the pools RPC call
      - Execute the summary RPC call
      - Execute the stats RPC call
8)  Parse all the RPC results from above and load to a Python datastructure (oStatsStructure)
9)  If there was no socket communications error with the Cointerra
      - Upload various stats on oStatsStructure to the MobileMiner Web API's.  Send stats for every configured MobileMiner
      - Check various stats on the oStatsStructure.  Set error flags and messages
11) Check the error and socketerror flags.  If there were errors
      - Check to see if error count is 3 or over.  If error count less than 3 go back to #7
      - Print error messages to the console and log file
      - Send a message to MobileMiner
      - SCP log files from the Cointerra machine
      - Reboot the cointerra
      - GZIP compress the log files
      - Create an email.  Attach the compressed log files
      - Delete the compressed files
      - Sleep for 2 minutes to wait for the Cointerra to come back online
      - Go back to #7
12) Sleep and wait for x period of time based on if machines were rebooted or not
