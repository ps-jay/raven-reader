#!/usr/bin/env python

import argparse
import signal
from RAVEnMQTT import RAVEnMQTT as raven
import sys
import logging as log

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
    log.basicConfig(format='%(asctime)s %(message)s', filename='raven.log', level=verbosityLevel)
  else:
    log.basicConfig(format='%(asctime)s %(message)s', level=verbosityLevel)

  # Initial log message
  log.info("Programme started.")

  # Initialise the class 
  global myWorker
  myWorker = raven(programArgs.device, programArgs.host, programArgs.port, programArgs.u, programArgs.P, programArgs.topic)
  if not myWorker.open():
    log.critical("Couldn't access resources needed. Check logs for more information.")
  else:
    # Register exit handler
    signal.signal(signal.SIGINT, exitSafely)

    myWorker.run()

if __name__ == '__main__':
  main()
