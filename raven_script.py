#!/usr/bin/env python

import argparse
import signal
from RAVEnMQTT import RAVEnMQTT as raven
import sys
import logging as log
import daemon.*

# This holds our RAVEn to MQTT class
myWorker = None

def argProcessing():
  '''Processes command line arguments'''
  parser = argparse.ArgumentParser(description="Rainforest Automation RAVEn Serial to MQTT Interface")
  parser.add_argument("--device", help="This is the serial port on which the RAVEn is available (default /dev/ttyUSB0)", default="/dev/ttyUSB0")
  parser.add_argument("--host", help="MQTT server hostname (default localhost)", default="localhost")
  parser.add_argument("--port", help="MQTT server port number (default 1883)", type=int, default=1883)
  parser.add_argument("-u", help="MQTT server username (omit for no auth)", default=None)
  parser.add_argument("-P", help="MQTT server password (default is empty)", default=None)
  parser.add_argument("topic", help="MQTT topic string to publish to")
  parser.add_argument("-v", help="Increase output verbosity", action="count", default=0)
  parser.add_argument("--logfile", help="Log to the specified file rather than STDERR", default=None, type=str)
  parser.add_argument("--daemon", help="Fork and run in background", default=None)
  parser.add_argument("--pidfile", help="PID file when run with --daemon (ignored otherwise)", default="/var/run/raven_script.pid")
  return parser.parse_args()

def exitSafely(signum, frame):
  '''SIGINT (Ctrl+C) handler'''
  global myWorker
  if myWorker is not None: 
    myWorker.close()
  log.info("Ctrl+C pressed. Exiting.")
  exit(0)

def main():
  # Process cmd line arguments
  programArgs = argProcessing()

  # Setup logging
  if programArgs.v > 5:
    verbosityLevel = 5
  else:
    verbosityLevel = programArgs.v
  verbosityLevel = (5 - verbosityLevel)*10
  if programArgs.logfile is not None:
    log.basicConfig(format='%(asctime)s %(message)s', filename=programArgs.logfile, level=verbosityLevel)
  else:
    log.basicConfig(format='%(asctime)s %(message)s', level=verbosityLevel)

  # Initial log message
  log.info("Programme started.")

  # Should we be daemonising?
  if programArgs.daemon is not None:
    dMon = DaemonContext()
    dMon.pidfile = programArgs.pidfile
    dMon.detach_process = True
    dMon.signal_map = { signal.SIGTTIN: None, signal.SIGTTOU: None, signal.SIGTSTP: None, signal.SIGTERM: 'exitSafely'}
    dMon.prevent_core = True


  # Initialise the class 
  global myWorker
  myWorker = raven(programArgs.device, programArgs.host, programArgs.port, programArgs.u, programArgs.P, programArgs.topic)
  if not myWorker.open():
    log.critical("Couldn't access resources needed. Check logs for more information.")
  else:
    # Register exit handler (only if in fg)
    if programArgs.daemon is None:
      signal.signal(signal.SIGINT, exitSafely)
    else:
      dMon.open()

    myWorker.run()

if __name__ == '__main__':
  main()
