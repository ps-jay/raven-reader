import sys
import time
import datetime
import calendar
import re
import xml.etree.ElementTree as ET
import logging as log
import serial
import sqlite3
import threading

class RAVEnSQLite:
    '''This class handles all communication to/from the RAVEn and the SQLite database'''

    def __init__(self, serDevice, db_file):
        '''The constructor requires all connection information for both SQLite and the RAVEn'''
        self._Y2K_SECONDS = calendar.timegm(datetime.datetime(2000, 01, 01, 00, 00, 00).utctimetuple())

        self.serDevice = serDevice
        self.database_file = db_file
        self.ser = None
        self.database = None
        self.cursor = None

        self._inst_timer_running = threading.Event()
        self._summ_timer_running = threading.Event()
        self._inst_timer = None
        self._summ_timer = None

        # Various Regex's
        self.reStartTag = re.compile('^<[a-zA-Z0-9]+>') # to find a start XML tag (at very beginning of line)
        self.reEndTag = re.compile('^<\/[a-zA-Z0-9]+>') # to find an end XML tag (at very beginning of line)

    def __del__(self):
        '''This will close all connections (serial/MQTT)'''
        self.close()

    def _openSerial(self):
        '''This function opens the serial port looking for a RAVEn. Returns True if successful, False otherwise.'''
        try:
            self.ser = serial.Serial(self.serDevice, 115200, serial.EIGHTBITS, serial.PARITY_NONE, timeout=0.5)
            self.ser.close()
            self.ser.open()
            self.ser.flushInput()
            self.ser.flushOutput()
            log.info("Connected to: " + self.ser.portstr)
            return True
        except Exception as e:
            log.critical("Cannot open serial port: " + str(e))
            return False

    def _openSQLite(self):
        '''This function will open a connection with the SQLite database'''
        self.database = sqlite3.connect(self.database_file)
        self.cursor = self.database.cursor()
        return True

    def _closeSerial(self):
        '''This function will close the serial port talking to the RAVEn'''
        if self.ser is not None:
            self.ser.close()
            log.info("Serial port closed.")
        else:
            log.debug("Asking to close serial port, but it was never open.")

    def _closeSQLite(self):
        '''This function will close the SQLite connection'''
        if self.database is not None:
            self.database.commit()
            self.cursor.close()
            self.database.close()
            log.info("SQLite connection was closed.")
        else:
            log.debug("Asking to close SQLite connection, but it was never open.")

    def open(self):
        '''This function will open all necessary connections for the RAVEn to talk to the SQLite database'''
        if not self._openSerial():
            log.critical("Serial port was not opened due to an error.")
            return False
        else:
            if not self._openSQLite():
                log.critical("SQLite connection was not opened due to an error.")
                return False
            else:
                return True

    def close(self):
        '''This function will close all previously opened connections & cancel timers'''
        self._inst_timer.cancel()
        self._summ_timer.cancel()
        if self.database is not None: self._closeSQLite()
        if self.ser is not None: self._closeSerial()

    def _isReady(self):
        '''This function is used to check if this object has been initialised correctly and is ready to process data'''
        return (self.database is not None) and (self.ser is not None)

    def _request_instant(self):
        SECONDS = 40.0
        if not self._inst_timer_running.is_set():
            self._inst_timer_running.set()
            self.ser.writelines(
                '<Command>'
                '  <Name>get_instantaneous_demand</Name>'
                '  <Refresh>Y</Refresh>'
                '</Command>'
            )
            log.debug("Requested an instantaneous demand reading")
            self._inst_timer = threading.Timer(SECONDS, self._inst_timer_running.clear)
            self._inst_timer.start()
            log.debug("Started a %d second back-off timer for instant demand reading requests" % SECONDS)

    def _request_summation(self):
        SECONDS = 20.0
        if not self._summ_timer_running.is_set():
            self._summ_timer_running.set()
            self.ser.writelines(
                '<Command>'
                '  <Name>get_current_summation_delivered</Name>'
                '  <Refresh>Y</Refresh>'
                '</Command>'
            )
            log.debug("Requested a current summation reading")
            self._summ_timer = threading.Timer(SECONDS, self._summ_timer_running.clear)
            self._summ_timer.start()
            log.debug("Started a %d second back-off timer for current summation reading requests" % SECONDS)

    def run(self):
        '''This function will read from the serial device, process the data and write to the SQLite database'''
        if self._isReady():
            # begin listening to RAVEn
            rawxml = ""

            while True:
                # Send requests (if timer has expired, see function definitions)
                self._request_instant()
                self._request_summation()
                # wait for /n terminated line on serial port (up to timeout)
                rawline = self.ser.readline()
                # remove null bytes that creep in immediately after connecting
                rawline = rawline.strip('\0')
                # only bother if this isn't a blank line
                if len(rawline) > 0:
                    # start tag
                    if self.reStartTag.match(rawline):
                        rawxml = rawline
                        log.debug("Start XML Tag found: " + rawline)
                    # end tag
                    elif self.reEndTag.match(rawline):
                        rawxml = rawxml + rawline
                        log.debug("End XML Tag Fragment found: " + rawline)
                        try:
                            xmltree = ET.fromstring(rawxml)
                            if xmltree.tag == 'InstantaneousDemand':
                                #self.database
                                #cursor.execute('''INSERT INTO %s
                                #                VALUES (?, ?, ?)''' % value, (int(unixTime), float(values[value]), int(0),))
                                #self.client.publish(self.topic, payload=self._getInstantDemandKWh(xmltree), qos=0)
                                log.warning(self._get_instant_demand(xmltree))
                            elif xmltree.tag == 'CurrentSummationDelivered':
                                log.warning(self._get_summation(xmltree))
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
                        # log.debug("Normal inner XML Fragment: " + rawline)
                else:
                  pass

        else:
            log.error("Was asked to begin reading/writing data without opening connections.")

    def _undo_twos(self, str_value, num_digits=None):
        '''Convert a twos complement hex string to a signed int'''
        if num_digits is not None:
            digits = len(str_value) - 2
        else:
            digits = num_digits
        pattern8 = '0x8'
        patternF = '0xF'
        for i in range(1, digits):
            pattern8 += '0'
            patternF += 'F'
        if int(str_value, 16) < int(pattern8, 16):
            n = int(str_value, 16)
        else:
            n = -1 * int(patternF, 16) + int(str_value, 16) -1
        return n

    def _get_summation(self, xmltree):
        '''Returns a dict with a struct_time and two floats:
            - timestamp: the timestamp
            - imported:  total imported kWh
            - exported:  total exported kWh'''
        hex_import = xmltree.find('SummationDelivered').text
        hex_export = xmltree.find('SummationReceived').text
        imported = float(self._undo_twos(hex_import, num_digits=16))
        exported = float(self._undo_twos(hex_export, num_digits=16))
        timestamp = int(xmltree.find('TimeStamp').text, 16)

        result = {
            'timestamp': self._get_raven_date(timestamp),
            'imported':  self._calculateRAVEnNumber(xmltree, imported),
            'exported':  self._calculateRAVEnNumber(xmltree, exported),
        }

        return result

    def _get_instant_demand(self, xmltree):
        '''Returns a struct_time and a float value for the current demand in Watts'''
        hex_demand = xmltree.find('Demand').text
        timestamp = int(xmltree.find('TimeStamp').text, 16)
        fDemand = float(self._undo_twos(hex_demand, num_digits=8))
        fResult = self._calculateRAVEnNumber(xmltree, fDemand)

        # x 1000 to convert kW -> W
        result = {
            'timestamp': self._get_raven_date(timestamp),
            'demand':    fResult * 1000,
        }

        return result

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
        return fResult

    def _get_raven_date(self, value):
        '''Returns a time stamp as a time.struct_time'''
        since_epoch = self._Y2K_SECONDS + value
        return time.gmtime(since_epoch)
