#!/usr/bin/env python

import sys
import serial
import time
import xml.etree.ElementTree as ET
import re
import mosquitto
import logging as log
import argparse

programArgs = "";

# Logging setup
log.basicConfig(filename='raven.log',level=log.DEBUG)

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
def onMosquittoConnect(mosq, userdata, rc):
  print rc
  if rc == 0:
    print "connected to MQTT ok"

def onMosquittoPublish(mosq, userdata, rc):
  print "Message sent!"

def argProcessing():
  '''Processes command line arguments'''
  parser = argparse.ArgumentParser(description="Rainforest Automation RAVEn Serial to MQTT Interface")
  parser.add_argument("--device", help="This is the serial port on which the RAVEn is available (default /dev/ttyUSB0)", default="/dev/ttyUSB0")
  parser.add_argument("--host", help="MQTT server hostname (default localhost)", default="localhost")
  parser.add_argument("--port", help="MQTT server port number (default 1883)", type=int, default=1883)
  parser.add_argument("-u", help="MQTT server username (omit for no auth)", default=None)
  parser.add_argument("-P", help="MQTT server password (default is empty)", default=None)
  parser.add_argument("topic", help="MQTT topic string to publish to")
  programArgs = parser.parse_args()

def main():
  argProcessing()
  # open serial port
  ser = serial.Serial(programArgs.device, 115200, serial.EIGHTBITS, serial.PARITY_NONE, timeout=0.5)
  try:
    ser.close()
    ser.open()
    ser.flushInput()
    ser.flushOutput()
    print("connected to: " + ser.portstr)
  except Exception as e:
    print "cannot open serial port: " + str(e)
    exit()
  
  # send initialize command to RAVEn (pg.9 of XML API Doc)
  #TODO: For some reason this command causes the error "Unknown command"?
  #sendCommand(ser, "initialise" )

  # setup mosquitto connection
  moz = mosquitto.Mosquitto("raven-usb-dongle", False)
  moz.on_connect = onMosquittoConnect
  moz.on_publish = onMosquittoPublish
  if programArgs.u is not None:
    moz.username_pw_set(programArgs.u, programArgs.p)
  moz.connect(programArgs.host, programArgs.port)

  rawxml = ""

  while True:
    # wait for /n terminated line on serial port (up to timeout)
    rawline = ser.readline()
    #log.debug("Received string from serial: [[" + rawline + "]]")
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
          #TODO: Eventually move this branching tree into a function or lookup table
          if xmltree.tag == 'InstantaneousDemand':
            moz.publish("sensors/frodo/power", getInstantDemandKWh(xmltree), 1)
            print getInstantDemandKWh(xmltree)
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
      log.debug("Skipped")

  #TODO: never gets called?
  ser.close()

if __name__ == '__main__':
  main()
