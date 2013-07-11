# Copyright 1996 by Sam Rushing
#
#                         All Rights Reserved
#
# Permission to use, copy, modify, and distribute this software and
# its documentation for any purpose and without fee is hereby
# granted, provided that the above copyright notice appear in all
# copies and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of Sam
# Rushing not be used in advertising or publicity pertaining to
# distribution of the software without specific, written prior
# permission.
#
# SAM RUSHING DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
# NO EVENT SHALL SAM RUSHING BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
# OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
#
# ... and, for the little added, also ...
#
#
# Copyright (C) 2005 Laurent A.V. Szyster
#
# This library is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
#    http://www.gnu.org/copyleft/gpl.html
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

"http://laurentszyster.be/blog/async_core/"

import exceptions, sys, os, time, socket, collections

from errno import (
        EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, 
        ENOTCONN, ESHUTDOWN, EINTR, EISCONN
        )

from allegra import loginfo, async_loop, finalization


class Dispatcher (loginfo.Loginfo, finalization.Finalization):
        
        connected = accepting = closing = False
        socket = addr = family_and_type = _fileno = None

        def create_socket (self, family, type):
                "create a socket and add the dispatcher to the I/O map"
                self.family_and_type = family, type
                self.socket = socket.socket (family, type)
                self.socket.setblocking (0)
                self._fileno = self.socket.fileno ()
                self.add_channel ()

        def set_connection (self, conn, addr):
                "set a connected socket and add the dispatcher to the I/O map"
                conn.setblocking (0)
                self.socket = conn
                self.addr = addr
                self._fileno = conn.fileno ()
                self.add_channel ()
                self.connected = True

        def set_reuse_addr (self):
                "try to re-use a server port if possible"
                try:
                        self.socket.setsockopt (
                                socket.SOL_SOCKET, 
                                socket.SO_REUSEADDR,
                                self.socket.getsockopt (
                                        socket.SOL_SOCKET, 
                                        socket.SO_REUSEADDR
                                        ) | 1
                                )
                except socket.error:
                        pass

        def listen (self, num):
                "listen and set the dispatcher's accepting state"
                self.accepting = True
                if os.name == 'nt' and num > 5:
                        num = 1
                return self.socket.listen (num)

        def bind (self, addr):
                "bind to addr and set the dispatcher's addr property"
                self.addr = addr
                return self.socket.bind (addr)

        def connect (self, address):
                "try to connect and set the dispatcher's connected state"
                err = self.socket.connect_ex (address)
                if err in (EINPROGRESS, EALREADY, EWOULDBLOCK):
                        return
                        
                if err in (0, EISCONN):
                        self.addr = address
                        self.connected = True
                        self.handle_connect ()
                else:
                        raise socket.error, err

        def accept (self):
                "try to accept a connection"
                try:
                        conn, addr = self.socket.accept()
                        return conn, addr
                        
                except socket.error, why:
                        if why[0] == EWOULDBLOCK:
                                pass
                        else:
                                raise
                        
        def close (self):
                "close the socket and remove the dispatcher from the I/O map"
                try:
                        self.socket.close ()
                except:
                        pass # closing a
                self.socket = None 
                self.del_channel ()
                self.connected = False
                self.closing = True # == (self.socket == None)
                assert None == self.log ('close', 'debug')

        # The transport API for stream and datagram sockets

        def send (self, data):
                "try to send data through a stream socket"
                try:
                        result = self.socket.send (data)
                        return result
                        
                except socket.error, why:
                        if why[0] == EWOULDBLOCK:
                                return 0
                                
                        else:
                                raise
                                
                        return 0

        def recv (self, buffer_size):
                "try to receive bytes from a stream socket or handle close"
                try:
                        data = self.socket.recv (buffer_size)
                        if not data:
                                # a closed connection is indicated by signaling
                                # a read condition, and having recv() return 0.
                                self.handle_close()
                                return ''
                                
                        else:
                                return data
                        
                except MemoryError:
                        # according to Sam Rushing, this is a place where
                        # MemoryError tend to be raised by Medusa. the rational 
                        # is that under high load, like a DDoS (or the /.
                        # effect :-), recv is the function that will be called 
                        # most *and* allocate the more memory.
                        #
                        sys.exit ("Out of Memory!") # do not even try to log!
                        
                except socket.error, why:
                        # winsock sometimes throws ENOTCONN
                        if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
                                self.handle_close()
                                return ''
                                
                        else:
                                raise

        def sendto (self, data, peer):
                "try to send data through a datagram socket"
                try:
                        return self.socket.sendto (data, peer)
                
                except socket.error, why:
                        if why[0] == EWOULDBLOCK:
                                return 0
                                
                        else:
                                raise
                                
                        return 0

        def recvfrom (self, datagram_size):
                "try to receive from a datagram socket, maybe handle close"
                try:
                        return self.socket.recvfrom (datagram_size)

                except socket.error, why:
                        if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
                                self.handle_close()
                                return '', None
                                
                        else:
                                raise

        # The "iner" API applied in async_loop

        async_map = async_loop._dispatched
    
        def add_channel (self):
                "add the dispatcher to the asynchronous I/O map"
                self.async_map[self._fileno] = self

        def del_channel (self):
                "removes the dispatcher from the asynchronous I/O map"
                fd = self._fileno
                try:
                        del self.async_map[fd]
                except KeyError:
                        pass

        def readable (self):
                "predicate for inclusion as readable in the poll loop"
                return True

        def writable (self):
                "predicate for inclusion as writable in the poll loop"
                return True

        def handle_read_event (self):
                "articulate read event as accept, connect or read."
                if self.accepting:
                        # for an accepting socket, getting a read implies
                        # that we are connected
                        #
                        # TODO: is this actually usefull? I mean, a listener
                        #       is not a stream connection, not really ...
                        #
                        if not self.connected:
                                self.connected = True
                        self.handle_accept ()
                elif not self.connected:
                        self.handle_connect ()
                        self.connected = True
                        self.handle_read ()
                else:
                        self.handle_read ()

        def handle_write_event (self):
                "articulate write event as connect or write."
                if not self.connected:
                        # getting a write implies that we are connected
                        self.handle_connect ()
                        self.connected = True
                self.handle_write ()
                
        # The protocol API for stream and datagram sockets

        def handle_error (self):
                "log a traceback and close, or raise SystemExit again"
                t, v = sys.exc_info ()[:2]
                if t is SystemExit:
                        raise t, v

                self.loginfo_traceback ()
                self.close () # self.handle_close () ... or nothing?

        def handle_close (self):
                self.close ()

        def handle_read (self):
                "to subclass: assert unhandled read event debug log"
                assert None == self.log ('unhandled read event', 'debug')

        def handle_write (self):
                "to subclass: assert unhandled write event debug log"
                assert None == self.log ('unhandled write event', 'debug')

        def handle_connect (self):
                "to subclass: assert unhandled connect event debug log"
                assert None == self.log ('unhandled connect event', 'debug')

        def handle_accept (self):
                "to subclass: assert unhandled accept event debug log"
                assert None == self.log ('unhandled accept event', 'debug')
                
        # and finaly ...

        def finalization (self, finalized):
                "assert debug log of the instance finalization"
                assert None == self.log ('finalized', 'debug')


# Asynchronous File I/O: UNIX pipe and stdio only
#
# What follows is the original comments by Sam Rushing:
#
# After a little research (reading man pages on various unixen, and
# digging through the linux kernel), I've determined that select()
# isn't meant for doing doing asynchronous file i/o.
# Heartening, though - reading linux/mm/filemap.c shows that linux
# supports asynchronous read-ahead.  So _MOST_ of the time, the data
# will be sitting in memory for us already when we go to read it.
#
# What other OS's (besides NT) support async file i/o?  [VMS?]
#
# Regardless, this is useful for pipes, and stdin/stdout...

if os.name == 'posix':
        import fcntl

        class File_wrapper (object):

                "wrap a file with enough of a socket like interface"

                def __init__ (self, fd):
                        self.fd = fd
        
                def recv (self, *args):
                        return apply (os.read, (self.fd, ) + args)
        
                def send (self, *args):
                        return apply (os.write, (self.fd, ) + args)
        
                read = recv
                write = send
        
                def close (self):
                        return os.close (self.fd)
        
                def fileno (self):
                        return self.fd
                        
        def set_file (self, fd):
                "set a file descriptor and add the dispatcher (POSIX only)"
                flags = fcntl.fcntl (fd, fcntl.F_GETFL, 0) | os.O_NONBLOCK
                fcntl.fcntl (fd, fcntl.F_SETFL, flags)
                self._fileno = fd
                self.socket = File_wrapper (fd)
                self.add_channel ()
                self.connected = True

        Dispatcher.set_file = set_file


# Conveniences

class Dispatcher_with_send (Dispatcher):
        
        ac_out_buffer_size = 1 << 14 # sweet sixteen kilobytes

        def __init__ (self):
                self.ac_out_buffer = ''
                
        def writable (self):
                "writable when there is output buffered or queued"
                return not (
                        (self.ac_out_buffer == '') and self.connected
                        )
        
        def handle_write (self):
                "try to send a chunk of buffered output or handle error"
                buffer = self.ac_out_buffer
                sent = self.send (buffer[:self.ac_out_buffer_size])
                if sent:
                        self.ac_out_buffer = buffer[sent:]
                else:
                        self.ac_out_buffer = buffer
                                                        

class Dispatcher_with_fifo (Dispatcher):

        ac_out_buffer_size = 1 << 14 # sweet sixteen kilobytes

        def __init__ (self):
                self.ac_out_buffer = ''
                self.output_fifo = collections.deque ()
                
        def writable (self):
                "writable when there is output buffered or queued"
                return not (
                        (self.ac_out_buffer == '') and
                        not self.output_fifo and self.connected
                        )
        
        def handle_write (self):
                """pull an output fifo of single strings into the buffer, 
                send a chunk of it or close if done"""
                obs = self.ac_out_buffer_size
                buffer = self.ac_out_buffer
                fifo = self.output_fifo
                while len (buffer) < obs and fifo:
                        s = fifo.popleft ()
                        if s == None:
                                if buffer == '':
                                        self.handle_close ()
                                        return
                                
                                else:
                                        fifo.append (None)
                                        break
        
                        buffer += s
                if buffer:
                        sent = self.send (buffer[:obs])
                        if sent:
                                self.ac_out_buffer = buffer[sent:]
                        else:
                                self.ac_out_buffer = buffer
                else:
                        self.ac_out_buffer = ''
                        
        def close_when_done (self):
                "queue None if there is output queued, or handle close now"
                if self.output_fifo:
                        self.output_fifo_push (None)
                else:
                        self.handle_close ()


# Note about this implementation
#
# This is a refactored version of the asyncore's original dispatcher class,
# with a new logging facility (loginfo). The poll functions and the
# asynchronous loop have been moved to async_loop, in a single module that
# integrates a non-blocking I/O loop, a heapq scheduler loop and a loop
# through a deque of finalizations.
#
# I also :
#
# 1. added set_connection (conn, addr), moving that logic out of __init__
# 2. refactored the File_dispatcher as a set_file (fd) method
# 3. removed the now redundant set_socket (sock) method.