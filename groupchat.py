import sys
import socket
import select
import time

import threadlogging

from queue import Queue
from threading import Thread

from networkio import TCPServer
from networkio import TCPSocketIOWorker
from networkio import ConnectionClosedByPeer




# TOOD: Use curses/ncurses? :)


MESSAGE_SIZE = 2**8

class ChatServer():
    def __init__(self, bindhost, bindport):
        self.bindhost = bindhost
        self.bindport = bindport
        self.clients = []

    def run(self):
        '''Starts the ChatServer, non-blocking call. Method returns control immediately to caller since the underlying TCPServer runs in a separate thread.'''
        _log.info('ChatServer now starting up')
        sockhandlers = (self.peer_connected, self.peer_msg_received, self.peer_disconnected)
        self.tcpserver = TCPServer(self.bindhost, self.bindport, sockhandlers, msgsize=MESSAGE_SIZE)
        self.tcpserver.run()

    def peer_connected(self, sockio):
        self.clients.append(sockio)
        msg = 'New user connected: {}'.format(sockio)
        _log.info(msg)
        self._server_msgall(msg, sockio)

    def peer_msg_received(self, sockio, msg):
        self._msgall(msg, sockio)

    def peer_disconnected(self, sockio):
        self.clients.remove(sockio)
        msg = 'User disconnected: {}'.format(sockio)
        _log.info(msg)
        self._server_msgall(msg, sockio)

    def shutdown(self):
        _log.info('ChatServer now shutting down')
        self.tcpserver.shutdown()

    def _server_msgall(self, msg, *exclude):
        msg = '>>> SERVER MSG: {}'.format(msg)
        self._msgall(msg, *exclude)

    def _msgall(self, msg, *exclude):
        '''Send a message to all connected clients, optionally specifying a list of clients to exclude from the message.'''
        targets = set(self.clients) - set(exclude)
        for sockio in targets:
            sockio.sendmsg(msg)


class CommandLineChatClient:
    PROMPT = '> '

    def __init__(self, username, desthost, destport):
        self.username = username
        self.desthost = desthost
        self.destport = destport

    # TODO: The func name "run" seems to imply async call in this
    # application. Change all occurrences of "run" with something else
    # for cases when it's a blocking call?
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.desthost, self.destport))
        sockhandlers = (self.peer_connected, self.peer_msg_received, self.peer_disconnected)
        self.sockio = TCPSocketIOWorker(sock, sockhandlers, msgsize=MESSAGE_SIZE)
        self.sockio_thread = Thread(target=self.sockio.run)
        self.sockio_thread.start()
        while True:
            try:
                msg = input(self.PROMPT)
                msg = '<{}> {}'.format(self.username, msg)
                self.sockio.sendmsg(msg)
            except KeyboardInterrupt:
                self._teardown()
                break

    def peer_connected(self, sockio):
        print('Connected to server ({})'.format(sockio))

    def peer_msg_received(self, sockio, msg):
        msg = msg.rstrip()

        sys.stdout.write('\r{}\n'.format(msg))
        # TODO: Not sure why I have to \r this one again.
        sys.stdout.write('\r{}'.format(self.PROMPT))

    def peer_disconnected(self, sockio):
        sys.stdout.write('CHAT SERVER CLOSED THE CONNECTION!\n')

    def _teardown(self):
        print('Tearing down connection')
        self.sockio.shutdown()
        self.sockio_thread.join()


_log = threadlogging.getlogger(__name__)

