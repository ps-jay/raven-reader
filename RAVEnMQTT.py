import sys
import time
import re
import xml.etree.ElementTree as ET
import logging as log
import serial
import paho.mqtt.client as mqtt

class RAVEnMQTT():
    '''This class handles all communication to/from the RAVEn and the MQTT     broker'''

    def __init__(self, serDevice, hostName, hostPort, hostUser, hostPwd, topic):
        '''The constructor requires all connection information for both MQTT and the RAVEn'''
        self.serDevice = serDevice
        self.hostName = hostName
        self.hostPort = hostPort
        self.hostUser = hostUser
        self.hostPwd = hostPwd
        self.topic = topic
        self.mqttNoGood = True
        self.mqttTimeout = 10
        self.hostKeepAlive = 60
        self.ser = None
        self.client = None

        # Various Regex's
        self.reStartTag = re.compile('^<[a-zA-Z0-9]+>') # to find a start XML tag (at very beginning of line)
        self.reEndTag = re.compile('^<\/[a-zA-Z0-9]+>') # to find an end XML tag (at very beginning of line)

    def __del__(self):
        '''This will close all connections (serial/MQTT)'''
        self.closeMQTT()
        log.info("Closed MQTT connection.")
        self.closeSerial()
        log.info("Closed serial port connection.")

    def _mqttOnPublish(self, client, userdata, mid):
        '''This is the event handler for when the MQTT message has been published'''
        log.debug("MQTT message sent.")

    def _mqttOnConnect(self, client, userdata, rc):
        '''This is the event handler for when one has connected to the MQTT broker. Will exit() if connect is not successful.'''
        if rc == 0:
            log.info("Connected to MQTT server successfully.")
            client.subscribe("$SYS/#")
            self.mqttNoGood = False
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
        self.closeSerial()
        self.mqttNoGood = True

    def _openSerial(self):
        '''This function opens the serial port looking for a RAVEn. Returns True if successful, False otherwise.'''
        try:
            self.ser = serial.Serial(programArgs.device, 115200, serial.EIGHTBITS, serial.PARITY_NONE, timeout=0.5)
            self.ser.close()
            self.ser.open()
            self.ser.flushInput()
            self.ser.flushOutput()
            log.info("Connected to: " + ser.portstr)
            return True
        except Exception as e:
            log.critical("Cannot open serial port: " + str(e))
            return False

    def _openMQTT(self):
        '''This function will open a connection with an MQTT broker'''
        self.client = mqtt.Client()
        self.client.on_connect = self._mqttOnConnect
        self.client.on_publish = self._mqttOnPublish
        if self.hostUser is not None:
            self.client.username_pw_set(self.hostUser, self.hostPwd)
        self.client.connect(self.hostName, self.hostPort, self.hostKeepAlive)
        if self.mqttNoGood:
            time.sleep(self.mqttTimeout)
            if self.mqttNoGood:
                self.client.disconnect()
                log.info("MQTT connection closed prematurely.")
                return False
        self.client.loop_start()
        return True

    def _closeSerial(self):
        '''This function will close the serial port talking to the RAVEn'''
        if self.ser is not None:
            self.ser.close()
            log.info("Serial port closed.")
        else:
            log.debug("Asking to close serial port, but it was never open.")

    def _closeMQTT(self):
        '''This function will close the MQTT connection'''
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()
            self.mqttNoGood = True
            log.info("MQTT connection was closed.")
        else:
            log.debug("Asking to close MQTT connection, but it was never open.")

    def open(self):
        '''This function will open all necessary connections for the RAVEn to talk to the MQTT broker'''
        if not self._openSerial():
            return
        else:
            if not self._openMQTT():
                return

    def close(self):
        '''This function will close all previously opened connections'''
        _closeMQTT()
        _closeSerial()

    def _isReady(self):
        '''This function is used to check if this object has been initialised correctly and is ready to process data'''
        return (self.client is not None) and (self.ser is not None)

    def run(self):
        '''This function will read from the serial device, process the data and publish MQTT messages'''
        if _isReady():
            # begin listening to RAVEn
            rawxml = ""

            while True:
                # wait for /n terminated line on serial port (up to timeout)
                rawline = self.ser.readline()
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
                                self.client.publish(programArgs.topic, payload=self._getInstantDemandKWh(xmltree), qos=0)
                                log.debug(self._getInstantDemandKWh(xmltree))
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
        else:
            log.error("Was asked to begin reading/writing data without opening connections.")

    def _getInstantDemandKWh(self, xmltree):
        '''Returns a single float value for the Demand from an Instantaneous Demand response from RAVEn'''
        # Get the Instantaneous Demand
        fDemand = float(int(xmltree.find('Demand').text,16))
        fResult = self._calculateRAVEnNumber(xmltree, fDemand)
        return fResult

    def _calculateRAVEnNumber(self, xmltree, value):
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