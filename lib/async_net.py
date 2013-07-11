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

"http://laurentszyster.be/blog/async_net/"

import collections, socket

from allegra import async_core


class NetstringError (Exception): pass

def collect_net (next, buffer, collect, terminate):
        "consume a buffer of netstrings into a stallable collector sink"
        lb = len (buffer)
        if next > 0:
                if next > lb:
                        collect (buffer)
                        return next - lb, '', False # buffer more ...

                if buffer[next] == ',':
                        collect (buffer[:next])
                        if terminate (None):
                                return 0, buffer[next+1:], True # stop now!
                        
                else:
                        raise NetstringError, '3 missing comma'
                
                prev = next + 1
        else:
                prev = 0
        while prev < lb:
                pos = buffer.find (':', prev)
                if pos < 0:
                        if prev > 0:
                                buffer = buffer[prev:]
                        if not buffer.isdigit ():
                                raise NetstringError, '1 not a netstring'
                        
                        return 0, buffer, False # buffer more ...
                        
                try:
                        next = pos + int (buffer[prev:pos]) + 1
                except:
                        raise NetstringError, '2 not a length'
                        
                if next >= lb:
                        collect (buffer[pos+1:])
                        return next - lb, '', False # buffer more
                
                elif buffer[next] == ',':
                        if terminate (buffer[pos+1:next]):
                                return 0, buffer[next+1:], True # stop now!
                        
                else:
                        raise NetstringError, '3 missing comma'
                      
                prev = next + 1 # continue ...
        return 0, '', False # buffer consumed.


class Dispatcher (async_core.Dispatcher):

        ac_in_buffer_size = ac_out_buffer_size = 1 << 14 # sweet 16 kilobytes

        terminator = 0
        collector_stalled = False
                
        def __init__ (self):
                self.ac_in_buffer = ''
                self.ac_out_buffer = ''
                self.output_fifo = collections.deque ()

        def __repr__ (self):
                return 'async-net id="%x"' % id (self)
                
        def readable (self):
                "predicate for inclusion in the poll loop for input"
                return not (
                        self.collector_stalled or
                        len (self.ac_in_buffer) > self.ac_in_buffer_size
                        )

        def writable (self):
                "predicate for inclusion in the poll loop for output"
                return not (
                        (self.ac_out_buffer == '') and
                        not self.output_fifo and self.connected
                        )

        def handle_read (self):
                "try to buffer more input and parse netstrings"
                try:
                        (
                                self.terminator, 
                                self.ac_in_buffer,
                                self.collector_stalled
                                ) = collect_net (
                                        self.terminator, 
                                        self.ac_in_buffer + self.recv (
                                                self.ac_in_buffer_size
                                                ),
                                        self.async_net_collect, 
                                        self.async_net_terminate
                                        )
                except NetstringError, error:
                        self.async_net_error (error)

        def handle_write (self):
                "buffer out a fifo of strings, try to send or close if done"
                obs = self.ac_out_buffer_size
                buffer = self.ac_out_buffer
                fifo = self.output_fifo
                while len (buffer) < obs and fifo:
                        strings = fifo.popleft ()
                        if strings == None:
                                if buffer == '':
                                        self.handle_close ()
                                        return
                                
                                else:
                                        fifo.append (None)
                                        break
        
                        buffer += ''.join ((
                                '%d:%s,' % (len (s), s) for s in strings
                                ))
                if buffer:
                        sent = self.send (buffer[:obs])
                        if sent:
                                self.ac_out_buffer = buffer[sent:]
                        else:
                                self.ac_out_buffer = buffer
                else:
                        self.ac_out_buffer = ''

        # A compatible interface with Async_chat.close_when_done used by
        # Allegra's TCP clients and servers implementation.
                        
        def close_when_done (self):
                """close this channel when previously queued strings have
                been sent, or close now if the queue is empty."""
                if self.output_fifo:
                        self.output_fifo.append (None)
                else:
                        self.handle_close ()

        # The Async_net Interface

        def async_net_out (self, strings):
                "buffer netstrings of an iterable of 8-bit byte strings"
                self.ac_out_buffer += ''.join ((
                        '%d:%s,' % (len (s), s) for s in strings
                        ))

        def async_net_push (self, strings):
                "push an iterable of 8-bit byte strings for output"
                assert hasattr (strings, '__iter__')
                self.output_fifo.append (strings)

        def async_net_pull (self):
                "try to consume the input netstrings buffered"
                if not self.ac_in_buffer:
                        self.collector_stalled = False
                        return
                
                try:
                        (
                                self.terminator, 
                                self.ac_in_buffer,
                                self.collector_stalled
                                ) = collect_net (
                                        self.terminator, 
                                        self.ac_in_buffer,
                                        self.async_net_collect, 
                                        self.async_net_terminate
                                        )
                except NetstringError, error:
                        self.async_net_error (error)

        async_net_in = ''

        def async_net_collect (self, bytes):
                "collect an incomplete netstring chunk into a buffer"
                self.async_net_in += bytes
                
        def async_net_terminate (self, bytes):
                "terminate a collected or buffered netstring and continue"
                if bytes == None:
                        bytes = self.async_net_in
                        self.async_net_in = ''
                return self.async_net_continue (bytes)

        def async_net_continue (self, bytes):
                "assert debug log of collected netstrings"
                assert None == self.log (bytes, 'async-net-continue')
                return False
        
        def async_net_error (self, message):
                "log netstrings error and close the channel"
                self.log (message, 'async-net-error')
                self.handle_close ()
                
                