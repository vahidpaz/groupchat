#!/usr/bin/env python3

import time
import logging
import argparse

import groupchat


_log = logging.getLogger()
_loghandler = None

def configlog(logfile):
    global _loghandler
    if not logfile:
        _loghandler = logging.StreamHandler()
    else:
        _loghandler = logging.FileHandler(logfile)

    _loghandler.setLevel(logging.DEBUG)
    _log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s [%(name)s] [%(threadName)s] %(message)s')
    _loghandler.setFormatter(formatter)
    _log.addHandler(_loghandler)

def main():
    parser = argparse.ArgumentParser(description='GroupChat Server',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--host', help='Hostname to bind server to', default='localhost')
    parser.add_argument('--port', help='Port number for server to listen on', type=int, default=27000)
    parser.add_argument('--log', help='File path to write logs to (defaults to stdout)', default='')
    args = parser.parse_args()

    configlog(args.log)

    server = groupchat.ChatServer(args.host, args.port)
    server.run()
    print('Press CTRL+C to exit')
    while True:
        try:
            input()
        except KeyboardInterrupt:
            server.shutdown()
            _log.info('Graceful shutdown of ChatServer complete')
            break
    _log.info('Application exiting')
    _loghandler.close()


if __name__ == '__main__':
    main()

