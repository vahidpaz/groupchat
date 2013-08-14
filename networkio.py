import time
import socket
import select
import logging
import threading
import sys

# TODO: Why does '.threadlogging' (relative import) not work even though
# the module is in the same dir?
import threadlogging

from queue import Queue
from threading import Thread




MSG_SIZE = 2**8
POLL_SLEEP = 0.25


def _exception_callback(exc_callback, reraise=True):
    '''Function decorator which saves you the trouble of putting a try-except block around the body of your own functions (why not receive a call when the exception occurs?). This decorator itself takes one or two parameters: exc_callback is a function to call back when the decorated function raises an exception; exc_callback will be passed a single argument (the exception instance). The second parameter to this decorator, reraise, instructs whether to re-raise the exception after the callback is complete.'''
    def decorator(decorated_func):
        def x(*args, **kwargs):
            try:
                decorated_func(*args, **kwargs)
            except Exception as e:
                exc_callback(e)
                if reraise: raise
        return x
    return decorator


def _log_exception(exc):
    _log.error('Caught the following exception', exc_info=exc)


class TCPServer:
    SERVER_SOCKET_BACKLOG_SIZE = 5

    def __init__(self, bindhost, bindport, sockhandlers,
                 msgsize=MSG_SIZE, pollsleep=POLL_SLEEP):
        self.bindhost = bindhost
        self.bindport = bindport
        self.sockhandlers = sockhandlers
        self.msgsize = msgsize
        self.pollsleep = pollsleep

        self._shutdown = False

        # TODO: Does this need to be thread safe?
        self.clients = {}

    def run(self):
        '''Asynchronously starts this server in a separate thread where it will be ready to accept incoming TCP connections.'''
        self.bossthread = Thread(target=self._run)
        self.bossthread.start()

    def shutdown(self):
        '''Initiates shutdown sequence for all server and worker threads, and waits until all have terminated.'''

        threads = list(self.clients.values()) + [self.bossthread]
        _log.info('Attempting to shutdown all {} threads'.format(len(threads)))

        self._shutdown = True

        # TODO: Edge case resulting in worker threads not being shutdown: It is possible that more elements will be added to self.clients after iterating through it here. Example: _handle_incoming() is currently running in a separate thread and is creating a new worker thread, we iterate through all existing worker threads here and shutdown(), soon after _handle_incoming() adds the new worker thread to the list, and finally it exists its method. We end up with 1 worker thread that is not shutdown. Locks/semaphores? :|
        for sockio in self.clients:
            sockio.shutdown()

        for thread in threads:
            thread.join()

    def __str__(self):
        return '{}({}:{})'.format(self.__class__, self.bindhost, self.bindport)

    def __repr__(self):
        return self.__str__()

    # We want to know when individual threads raise exceptions so we can
    # log the issue rather than having it only display to stderr.
    @_exception_callback(_log_exception)
    def _run(self):
        _log.logcontext.val = 'Server Thread'

        self.serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # The SO_REUSEADDR flag tells the kernel to reuse a local socket
        # in TIME_WAIT state, without waiting for its natural timeout to
        # expire. If this is not specified then when a new process tries to
        # rebind/reuse this port it will result in the following error:
        #   OSError: [Errno 98] Address already in use
        self.serversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.serversock.bind((self.bindhost, self.bindport))
        self.serversock.listen(self.SERVER_SOCKET_BACKLOG_SIZE)
        _log.info('Now listening for incoming connections on {}:{}'.format(self.bindhost, self.bindport))

        while not self._shutdown:
            # No new connections to accept? Then take a nap so you don't
            # overwork yourself. If a new connection _is_ handled, then
            # be able to handle bursts by not sleeping at all until it
            # gets quiet.
            if not self._handle_incoming():
                time.sleep(self.pollsleep)

        # TODO: This server socket close() seems necessary else the
        # bind() will remain. Why isn't it documented anywhere?
        self.serversock.close()

        # TODO: Can a server socket be close()'ed while client connections are still established?

        _log.info('Server thread about to terminate')

    def _handle_incoming(self):
        '''Returns False immediately (non-blocking) if no new connection is available to be accepted. Otherwise accepts one (and only 1) new connection, launches a worker thread for it, and returns True. Due to the nature of select(), it is possible that this call will block (though very unlikely).'''
        # TODO: Is there a way to be notified by the OS/kernel when a socket is ready for reading, rather than polling?
        rlist, wlist, xlist = select.select([self.serversock], [], [], 0)
        if not rlist:
            return False
        clientsock, clientaddr = self.serversock.accept()
        sockhandlers = (self.peer_connected, self.peer_msg_received, self.peer_disconnected)
        client = TCPSocketIOWorker(clientsock, sockhandlers, msgsize=self.msgsize, pollsleep=self.pollsleep)
        _log.info('New connection established with client: {}:{}'.format(clientaddr[0], clientaddr[1]))

        t = Thread(target=client.run)
        t.start()
        self.clients[client] = t

        return True

    def peer_connected(self, sockio):
        self.sockhandlers[0](sockio)

    def peer_msg_received(self, sockio, msg):
        self.sockhandlers[1](sockio, msg)

    def peer_disconnected(self, sockio):
        # TODO: Will Future.add_done_callback() make this look nicer?
        del self.clients[sockio]
        self.sockhandlers[2](sockio)



# TODO: Refactor this class so that it supports byte and string I/O. The string I/O should be UTF8 only. Make sure to encode strings before sending to know their byte size. First goal can be to fully support UTF8 so that clients can ultimately use their own locale. Client will be responsible for encoding and making sure the right fixed packet size is transmitted for whatever their input utf8 string is. Server will always look for a fixed packet size in bytes, and decode the content as utf8 (which makes it into a Python str type), and broadcast that str to other clients (again, encoding it as utf8, measuring size, sending that to each of the clients).
class TCPSocketIOWorker:
    '''Handles sending and receiving ASCII data for a (client) socket. To be run in its own thread.'''

    def __init__(self, clientsock, sockhandlers,
                 pollsleep=POLL_SLEEP, msgsize=MSG_SIZE, msgpadding=' '):
        self.clientsock = clientsock
        self.clientaddr = clientsock.getpeername()
        self.peer_connected, self.peer_msg_received, self.peer_disconnected = sockhandlers
        self.pollsleep = pollsleep
        self.msgpadding = msgpadding
        self.msgsize = msgsize
        self._outgoingmsgq = Queue()

        assert len(self.msgpadding) == 1
        self._shutdown = False

    # We want to know when individual threads raise exceptions so we can
    # log the issue rather than having it only display to stderr.
    @_exception_callback(_log_exception)
    def run(self):
        addrinfo = '{}:{}'.format(self.clientaddr[0], self.clientaddr[1])
        _log.logcontext.val = addrinfo
        _log.info('New thread now running to handle connection: {}'.format(addrinfo))

        self.peer_connected(self)

        # Loop until told to stop. In each iteration process at most one
        # (and only 1) outgoing message, and at most one incoming
        # message. This small amount of work allows us to respond to
        # shutdown requests in a timely fashion (otherwise we may be
        # busy processing I/O and starve the shutdown request).
        while not self._shutdown:
            try:
                # If there is data neither for sending nor receiving,
                # then take a quick nap. Otherwise keep processing I/O
                # while one (or both) is processed.
                if (not self._handle_outgoing()) and (not self._handle_incoming()):
                    time.sleep(self.pollsleep)
            except ConnectionClosedByPeer:
                _log.info('Connection has been closed by remote peer')
                self.peer_disconnected(self)
                break

        self._closesocket()
        _log.info('SocketIO thread about to terminate')

    def _closesocket(self):
        self.clientsock.shutdown(socket.SHUT_RDWR)
        self.clientsock.close()

    # TODO: Should this invoke the peerdisconnected callback?
    # TODO: Make this into a data attribute? Or does it look more like a real public API as a method?
    def shutdown(self):
        self._shutdown = True

    # TODO: Split out methods for: sendbytes and sendstr? Clearer. Plus, bytes is the "real" format for network I/O.
    def sendmsg(self, msg):
        '''Queues a textual message to be sent to remote peer. Input msg should be an str data type. This method always returns immediately without actually having sent the message (asynchronous).'''
        self._outgoingmsgq.put(msg)

    def _recvmsg(self):
        '''Blocks until a single message is received from the remote peer.'''
        _log.debug('recvmsg(): Now attempting to receive a msg from client')
        msg = bytearray()
        while len(msg) < self.msgsize:
            chunk = self.clientsock.recv(self.msgsize - len(msg))
            if not chunk: raise ConnectionClosedByPeer()
            msg.extend(chunk)
        # Return value as string.
        result = msg.decode()
        _log.debug('recvmsg(): Msg received: {}'.format(result.rstrip()))
        return result

    # TODO: What's the diff between __repr__ and __str__?
    def __str__(self):
        return '{}({}:{})'.format(self.__class__, self.clientaddr[0], self.clientaddr[1])

    def __repr__(self):
        return self.__str__()

    def _handle_outgoing(self):
        '''Attempt to send 1 message to remote peer. If no messages are queued to send out, then return immediatley. Return True if there was 1 message and it was sent, otherwise False. This method always a non-blocking call.'''
        if self._outgoingmsgq.qsize() == 0:
            return False
        self._sendmsg(self._outgoingmsgq.get())
        self._outgoingmsgq.task_done()
        return True

    def _handle_incoming(self):
        '''Attempt to read 1 message from the socket's remote peer. If there is no message to read, then return immediately without blocking. Return True if there was 1 message and it was read, otherwise False. Note that there _is_ a chance that this method will block indefintely due to the way in which select() works to determine if there is data to read on the socket. As one developer put it, select() indicates readability or writability "as-close-to-certain-as-we-ever-get-in-this-business".'''
        # TODO: Why can't the timeout arg be passed in as a keyword arg?
        rlist, wlist, xlist = select.select([self.clientsock], [], [], 0)
        # Does the socket likely have data that can be read? If not don't bother trying to read, otherwise recv() will block.
        if not rlist:
            return False
        msg = self._recvmsg()
        # TODO: Would it be better to launch a separate thread or something when issuing these callbacks? What happens if the callback performs a long-running task? Then our I/O worker is not processing new data!
        self.peer_msg_received(self, msg)
        return True

    def _sendmsg(self, msg):
        _log.debug('sendmsg(): Now sending a msg to client: {}'.format(msg.rstrip()))
        msg = msg.encode()

        # Pad msg to fill fixed msg size requirement.
        # TODO: This can be done better. Padding char might consume more than 1 byte (but this code assumes 1 byte). The following truncate will fix. But a better way?
        if len(msg) < self.msgsize:
            # TODO: Should msg be a bytearray since we are maniuplating
            # a bit?
            padbytes = (self.msgpadding * (self.msgsize - len(msg))).encode()
            msg += padbytes

        # Truncate oversized msgs.
        # TODO: Raise error instead?
        if len(msg) > self.msgsize:
            msg = msg[:self.msgsize]

        assert len(msg) == self.msgsize

        totalsent = 0
        while totalsent < self.msgsize:
            # TODO: Socket HowTo says that flushing is needed to
            # actually send the data out of the buffer. How's that
            # done??
            sent = self.clientsock.send(msg[totalsent:])
            if not sent: raise ConnectionClosedByPeer()
            totalsent += sent

        _log.debug('sendmsg(): Done sending msg')


class ConnectionClosedByPeer(Exception):
    pass


_log = threadlogging.getlogger(__name__)

