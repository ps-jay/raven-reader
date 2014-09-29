
Overview
========

I was looking for a quick way to get the Rainforest Automation RAVEn talking to an MQTT broker, and I came across frankp's  package from the Rainforest Automation site. I wasn't very keen on having config variables in the script so I cleaned them out and put all that onto the command line (my preference). I also added a bit more error handling (not much more though). I also migrated from the from the mosquitto python package to the Paho one - seemed like the latter may be more active and I was getting some strange behaviour (connection drop-outs) with mosquitto that seem to have disappeared with Paho.

Resources
=========

Here are some links from around the place connected or used with this project:

The XML API Documentation for communicating with the Rainforest Automation RAVEn:
http://www.rainforestautomation.com/sites/default/files/download/rfa-z106/raven_xml_api_r127.pdf

Paho's Python Client Documentation:
http://www.eclipse.org/paho/clients/python/docs/

Releases
========
**v2.0.0**: Rewritten from the ground up to improve maintenance, feature additions and error handling.
**v1.0.0**: This is the initial release based on an older set of scripts. I recommend going to v2 for better error handling and MQTT management.

Branches
========

**master**: the latest stable version; bug fixes only
**devel**: bleeding edge; may be broken; development happens here
