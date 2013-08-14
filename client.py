#!/usr/bin/env python3

import sys
import logging
import argparse

import groupchat




_log = logging.getLogger()
_loghandler = None

def configlog(logfile):
    global _loghandler
    _loghandler = logging.FileHandler(logfile)
    _loghandler.setLevel(logging.DEBUG)

    _log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s [%(name)s] [%(threadName)s] %(message)s')
    _loghandler.setFormatter(formatter)
    _log.addHandler(_loghandler)

def main():
    parser = argparse.ArgumentParser(description='GroupChat Command-Line Client',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('username', help='The username you want to go by')
    parser.add_argument('--host', help='Server hostname to connect to', default='localhost')
    parser.add_argument('--port', help='Server port number to connect to', type=int, default=27000)
    parser.add_argument('--log', help='File path to write logs to', default='/dev/null')
    args = parser.parse_args()

    configlog(args.log)
    client = groupchat.CommandLineChatClient(args.username, args.host, args.port)
    client.run()
    _loghandler.close()


if __name__ == '__main__':
    main()

