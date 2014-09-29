Overview
========

This talks to a Rainforest Automation RAVEn USB stick to obtain Zigbee smart metering data.
It then write it to a SQLite database for further analysis by other applications.

I've adapted the code from: https://github.com/rub-a-dub-dub/python-raven
Which itself is a fork of: https://github.com/frankp/python-raven

I 'forked' from commit 6295e5ff9f669a683e9850ae41e301a83649820c.


Adaptions from python-raven
===========================

# Write to SQLite not MQTT
# Threading to obtain both instant demand and current summation readins


Resources
=========

The XML API Documentation for communicating with it:
http://www.rainforestautomation.com/sites/default/files/download/rfa-z106/raven_xml_api_r127.pdf
