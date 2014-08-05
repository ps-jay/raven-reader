#!/usr/bin/env python

import sys
import serial
import time
import xml.etree.ElementTree as ET
import re
import logging as log
import argparse
import paho.mqtt.client as mqtt

# Various Regex's
reStartTag = re.compile('^<[a-zA-Z0-9]+>') # to find a start XML tag (at very beginning of line)
reEndTag = re.compile('^<\/[a-zA-Z0-9]+>') # to find an end XML tag (at very beginning of line)

def sendCommand(serialport, command):
  '''Given a command it will be formatted in XML and written to serialport for RAVEn device'''
  # Sends a simple command, such as initialize, get_instantaneous_demand, etc.
  output = ("<Command>\n  <Name>%s</Name>\n</Command>" % command)
  log.info("Issuing command: " + command)
  serialport.write(output)
  time.sleep(0.5) # allow this command to sink in

def getInstantDemandKWh(xmltree):
  '''Returns a single float value for the Demand from an Instantaneous Demand response from RAVEn'''
  # Get the Instantaneous Demand
  fDemand = float(int(xmltree.find('Demand').text,16))
  fResult = calculateRAVEnNumber(xmltree, fDemand)
  return fResult

def calculateRAVEnNumber(xmltree, value):
  '''Calculates a float value from RAVEn using Multiplier and Divisor in XML response'''
  # Get calculation parameters from XML - Multiplier, Divisor
  fDivisor = float(int(xmltree.find('Divisor').text,16))
  fMultiplier = float(int(xmltree.find('Multiplier').text,16))
  if (fMultiplier > 0 and fDivisor > 0):
    fResult = float( (value * fMultiplier) / fDivisor)
  elif (fMultiplier > 0):
    fResult = float(value * fMultiplier)
  else: # (Divisor > 0) or anything else
    fResult = float(value / fDivisor)
  return fResult*1000

# Callback for MQTT Client
#TODO: This isn't working??
def on_connect(client, userdata, rc):
  '''Event handler for when the MQTT connection is made'''
  if rc == 0:
    log.info("Connected to server.")
    client.subscribe("$SYS/#")
    return
  elif rc == 1:
    log.critical("Connection to server refused - incorrect protocol version.")
  elif rc == 2:
    log.critical("Connection to server refused - invalid client identifier.")
  elif rc == 3:
    log.critical("Connection to server refused - server unavailable.")
  elif rc == 4:
    log.critical("Connection to server refused - bad username or password.")
  elif rc == 5:
    log.critical("Connection to server refused - not authorised.")
  elif rc >=6 :
    log.critical("Reserved code received!")
  ser.close()
  exit()

#def on_publish(client, userdata, mid):
#  '''Event handler for when the MQTT message is published'''
#  print("Sent message")

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

def main():
  # Process cmd line arguments
  programArgs = argProcessing()

  # Setup logging
  if programArgs.v > 5:
    verbosityLevel = 5
  else:
    verbosityLevel = programArgs.v
  verbosityLevel = (5 - verbosityLevel)*10
  log.basicConfig(format='%(asctime)s %(message)s')
  if programArgs.logfile is not None:
    log.basicConfig(filename='raven.log',level=verbosityLevel)

  log.info("Programme started.")
  
  # open serial port
  try:
    ser = serial.Serial(programArgs.device, 115200, serial.EIGHTBITS, serial.PARITY_NONE, timeout=0.5)
    ser.close()
    ser.open()
    ser.flushInput()
    ser.flushOutput()
    log.info("connected to: " + ser.portstr)
  except Exception as e:
    log.critical("cannot open serial port: " + str(e))
    exit()
  
  # send initialize command to RAVEn (pg.9 of XML API Doc)
  #TODO: For some reason this command causes the error "Unknown command"?
  #sendCommand(ser, "initialise" )

  # setup mqtt connection
  client = mqtt.Client();
  client.on_connect = on_connect;
  #client.on_publish = on_publish;
  if programArgs.u is not None:
    client.username_pw_set(programArgs.u, programArgs.P)
  client.connect(programArgs.host, programArgs.port, 60)

  # begin listening to RAVEn
  rawxml = ""

  while True:
    # wait for /n terminated line on serial port (up to timeout)
    rawline = ser.readline()
    # remove null bytes that creep in immediately after connecting
    rawline = rawline.strip('\0')
    # only bother if this isn't a blank line
    if len(rawline) > 0:
      # start tag
      if reStartTag.match(rawline):
        rawxml = rawline
        log.debug("Start XML Tag found: " + rawline)
      # end tag
      elif reEndTag.match(rawline):
        rawxml = rawxml + rawline
        log.debug("End XML Tag Fragment found: " + rawline)
        try:
          xmltree = ET.fromstring(rawxml)
          if xmltree.tag == 'InstantaneousDemand':
            client.publish(programArgs.topic, payload=getInstantDemandKWh(xmltree), qos=0)
            log.debug(getInstantDemandKWh(xmltree))
          else:
            log.warning("*** Unrecognised (not implemented) XML Fragment")
            log.warning(rawxml)
        except Exception as e:
          log.error("Exception triggered: " + str(e))
        # reset rawxml
        rawxml = ""
      # if it starts with a space, it's inside the fragment
      else:
        rawxml = rawxml + rawline
        log.debug("Normal inner XML Fragment: " + rawline)
    else:
      log.warning("Skipped an XML fragment since it was malformed.")

  #TODO: never gets called?
  ser.close()

if __name__ == '__main__':
  main()
