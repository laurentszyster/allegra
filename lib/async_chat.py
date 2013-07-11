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

"http://laurentszyster.be/blog/async_chat/"

import collections, socket

from allegra import async_core


def find_prefix_at_end (haystack, needle):
        "given 'haystack', see if any prefix of 'needle' is at its end."
        l = len (needle) - 1
        while l and not haystack.endswith (needle[:l]):
                l -= 1
        return l


def collect_chat (c, buffer):
        "collect a buffer for a channel or collector"
        lb = len (buffer)
        while lb:
                terminator = c.get_terminator ()
                if terminator is None or terminator == '':
                        c.collect_incoming_data (buffer)
                        buffer = ''
                elif isinstance (terminator, int):
                        if lb < terminator:
                                c.collect_incoming_data (buffer)
                                buffer = ''
                                c.set_terminator (terminator - lb)
                        else:
                                c.collect_incoming_data (buffer[:terminator])
                                buffer = buffer[terminator:]
                                c.set_terminator (0)
                                if c.found_terminator ():
                                        c.collector_stalled = True
                                        break

                else:
                        tl = len (terminator)
                        index = buffer.find (terminator)
                        if index != -1:
                                if index > 0:
                                        c.collect_incoming_data (
                                                buffer[:index]
                                                )
                                buffer = buffer[index+tl:]
                                if c.found_terminator ():
                                        c.collector_stalled = True
                                        break
                                
                        else:
                                index = find_prefix_at_end (
                                        buffer, terminator
                                        )
                                if index:
                                        if index != lb:
                                                c.collect_incoming_data (
                                                        buffer[:-index]
                                                        )
                                                buffer = buffer[-index:]
                                        break
                                        
                                else:
                                        c.collect_incoming_data (buffer)
                                        buffer = ''
                lb = len (buffer)
        return buffer


class Dispatcher (async_core.Dispatcher):

        ac_in_buffer_size = ac_out_buffer_size = 1 << 14
        
        terminator = None
        collector_stalled = False
        collector_is_simple = False
        collector_depth = 32
        
        def __init__ (self):
                self.ac_in_buffer = ''
                self.ac_out_buffer = ''
                self.output_fifo = collections.deque ()

        def __repr__ (self):
                return 'async-chat id="%x"' % id (self)
        
        def readable (self):
                "predicate for inclusion in the poll loop for input"
                return not (
                        self.collector_stalled or
                        len (self.ac_in_buffer) > self.ac_in_buffer_size
                        )

        def writable (self):
                "predicate for inclusion in the poll loop for output"
                try:
                        return not (
                                self.output_fifo[
                                        0
                                        ].producer_stalled () and
                                self.connected
                                )
                
                except:
                        return not (
                                (self.ac_out_buffer == '') and 
                                not self.output_fifo and 
                                self.connected
                                )

        def handle_read (self):
                "try to refill the input buffer and collect it"
                try:
                        data = self.recv (self.ac_in_buffer_size)
                except socket.error, why:
                        self.handle_error ()
                        return

                self.ac_in_buffer = collect_chat (
                        self, self.ac_in_buffer + data
                        )

        def handle_write (self):
                "maybe refill the output buffer and try to send it"
                obs = self.ac_out_buffer_size
                buffer = self.ac_out_buffer
                if len (buffer) < obs:
                        fifo = self.output_fifo
                        while fifo:
                                p = fifo[0]
                                if p == None:
                                        if buffer == '':
                                                fifo.popleft ()
                                                self.handle_close () 
                                                return
                                        
                                        break
                                    
                                elif type (p) == str:
                                        fifo.popleft ()
                                        buffer += p
                                        if len (buffer) < obs:
                                                continue
                                        
                                        break
                                
                                if p.producer_stalled ():
                                        break
                                
                                data = p.more ()
                                if data:
                                        buffer += data
                                        break
                                    
                                fifo.popleft ()
                if buffer:
                        sent = self.send (buffer[:obs])
                        if sent:
                                self.ac_out_buffer = buffer[sent:]
                        else:
                                self.ac_out_buffer = buffer
                else:
                        self.ac_out_buffer = ''
                        
        def close (self):
                "close the dispatcher and maybe terminate the collector"
                async_core.Dispatcher.close (self)
                if not self.collector_stalled:
                        depth = self.collector_depth
                        while depth and not self.found_terminator (): 
                                depth -= 1
                        if depth < 1:
                                self.log (
                                        '%d' % self.collector_depth,
                                        'collector-leak'
                                        )
                        
        def close_when_done (self):
                """automatically close this channel once the outgoing queue 
                is empty, or handle close now if it is allready empty"""
                if self.output_fifo:
                        self.output_fifo.append (None)
                else:
                        self.handle_close () # when done is now!

        def async_chat_push (self, p):
                "push a string or producer on the output deque"
                assert type (p) == str or hasattr (p, 'more')
                self.output_fifo.append (p)
                
        # push_with_producer = push = async_chat_push

        def async_chat_pull (self):
                "stall no more and collect the input buffer"
                self.collector_stalled = False
                if self.ac_in_buffer:
                        self.ac_in_buffer = collect_chat (
                                self, self.ac_in_buffer
                                )

        def set_terminator (self, terminator):
                "set the channel's terminator"
                self.terminator = terminator

        def get_terminator (self):
                "get the channel's terminator"
                return self.terminator

        def collect_incoming_data (self, data):
                "assert debug log of collected data"
                assert None == self.log (data, 'collect-incoming-data')

        def found_terminator (self):
                "assert debug log of terminator found"
                assert None == self.log (
                        self.get_terminator (), 'found-terminator'
                        )
                return True # do not pipeline 
        
# Note about this implementation
#
# This is a refactored version of asynchat.py as found in Python 2.4, and
# modified as to support stallable producers and collectors, loginfo and 
# finalization.
#
# Stallable Producer and Collector
#
# In order to support non-blocking asynchronous and synchronized peer, 
# the async_chat module introduces stallable collector and generalize
# the stallable producer of Medusa's proxy.
#
# Besides the fact that stallable reactors are a requirement for peers
# that do not block, they have other practical benefits. For instance,
# a channel with an collector_stalled and an empty output_fifo will not
# be polled for I/O.
#
# This implementation use collection.deque for output FIFO queues instead 
# of a class wrapper, and the push () method actually does what it is 
# supposed to do and pushes a string at the end that output queue, not a 
# Simple instance.
#
# The channel's method collect_incoming_data is called to collect data 
# between terminators. Its found_terminator method is called whenever
# the current terminator is found, and if that method returns True, then
# no more buffer will be consumed until the channel's collector_stalled
# is not set to False by a call to async_collect.
