#!/usr/bin/env python

import argparse
import signal
from RAVEnSQLite import RAVEnSQLite as raven
import sys
import logging as log
from daemon import DaemonContext

# This holds our RAVEn to SQLite class
myWorker = None


def argProcessing():
    '''Processes command line arguments'''
    parser = argparse.ArgumentParser(
        description="Rainforest Automation RAVEn Serial to SQLite",
    )
    parser.add_argument("--device", "-d",
        help="This is the serial port on which the RAVEn is available (default /dev/ttyUSB0)",
        default="/dev/ttyUSB0",
    )
    parser.add_argument("-v",
        help="Increase output verbosity",
        action="count",
        default=0,
    )
    parser.add_argument("--logfile", "-l",
        help="Log to the specified file rather than STDERR",
        default=None,
        type=str,
    )
    parser.add_argument("--daemon",
        help="Fork and run in background",
        default=None,
    )
    parser.add_argument("--pidfile", "-p",
        help="PID file when run with --daemon (ignored otherwise)",
        default="/var/run/raven_script.pid",
    )
    parser.add_argument("--database", "-f",
        help="SQLite database file to write to",
        default="/srv/energy/meter.sqlite",
    )
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
        log.basicConfig(
            format='%(asctime)s %(message)s',
            filename=programArgs.logfile,
            level=verbosityLevel
        )
    else:
        log.basicConfig(
            format='%(asctime)s %(message)s',
            level=verbosityLevel
        )

    # Initial log message
    log.info("Programme started.")

    # Should we be daemonising?
    if programArgs.daemon is not None:
        dMon = DaemonContext()
        dMon.pidfile = programArgs.pidfile
        dMon.detach_process = True
        dMon.signal_map = {
            signal.SIGTTIN: None,
            signal.SIGTTOU: None,
            signal.SIGTSTP: None,
            signal.SIGTERM: 'exitSafely',
        }
        dMon.prevent_core = True

    # Initialise the class
    global myWorker
    myWorker = raven(programArgs.device, programArgs.database)
    if not myWorker.open():
        log.critical(
            "Couldn't access resources needed. Check logs for more"
            "information."
        )
    else:
        # Register exit handler (only if in fg)
        if programArgs.daemon is None:
            signal.signal(signal.SIGINT, exitSafely)
        else:
            dMon.open()

        myWorker.run()

if __name__ == '__main__':
    main()
