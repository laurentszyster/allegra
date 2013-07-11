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
# it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA

"http://laurentszyster.be/blog/select_trigger/"

import sys, os, socket, thread

from allegra import (
	netstring, prompt, loginfo, 
        async_loop, finalization, async_core
        )


class Trigger (async_core.Dispatcher):

        "Thunk back safely from threads into the asynchronous loop"
        
        def __repr__ (self):
                return 'trigger id="%x"' % id (self)

        def readable (self):
                "a Trigger is allways readable"
                return True

        def writable (self):
                "a Trigger is never writable"
                return False

        def handle_connect (self):
                "pass on connect"
                pass

        def handle_read (self):
                "try to call all thunked, log all exceptions' traceback"
                try:
                        self.recv (8192)
                except socket.error:
                        return
                
                self.lock.acquire ()
                try:
                        thunks = self.thunks
                        self.thunks = []
                finally:
                        self.lock.release ()
                for thunk in thunks:
                        try:
                                thunk[0] (*thunk[1])
                        except:
                                self.loginfo_traceback ()
                        

if os.name == 'posix':

        def posix_trigger_init (self):
                "use a POSIX pipe to connect a pair of file descriptors"
                self.select_triggers = 0
                fd, self.trigger = os.pipe ()
                self.set_file (fd)
                self.lock = thread.allocate_lock ()
                self.thunks = []
                assert None == self.log ('open', 'debug')

        def posix_trigger_pull (self, thunk):
                "acquire the trigger's lock, thunk and pull"
                self.lock.acquire ()
                try:
                        self.thunks.append (thunk)
                finally:
                        self.lock.release ()
                os.write (self.trigger, 'x')
        
        def posix_trigger_close (self):
                "close the trigger"
                async_core.Dispatcher.close (self)
                os.close (self.trigger)

        Trigger.__init__ = posix_trigger_init
        Trigger.__call__ = posix_trigger_pull
        Trigger.close = posix_trigger_close
                                
elif os.name == 'nt':

        def win32_trigger_init (self):
                "get a pair of Win32 connected sockets"
                self.select_triggers = 0
                a = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
                w = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
                a.bind (('127.9.9.9', 19999))
                a.listen (1)
                w.setblocking (0)
                try:
                        w.connect (('127.9.9.9', 19999))
                except:
                        pass
                conn, addr = a.accept ()
                a.close ()
                w.setblocking (1)
                self.trigger = w
                self.set_connection (conn, addr)
                self.lock = thread.allocate_lock ()
                self.thunks = []
                assert None == self.log ('open', 'debug')

        def win32_trigger_pull (self, thunk):
                "acquire the trigger's lock, thunk and pull"
                self.lock.acquire ()
                try:
                        self.thunks.append (thunk)
                finally:
                        self.lock.release ()
                self.trigger.send ('x')

        def win32_trigger_close (self):
                "close the trigger"
                async_core.Dispatcher.close (self)
                self.trigger.close ()

        Trigger.__init__ = win32_trigger_init
        Trigger.__call__ = win32_trigger_pull
        Trigger.close = win32_trigger_close

else:
	raise ImportError ('OS "%s" not supported, sorry :-(' % os.name)


class Select_trigger (loginfo.Loginfo, finalization.Finalization):
	
	"""A base class that implements the select_trigger interface
	
		select_trigger ((function, args))
	
	to thunk function and method calls from one thread into the main
	asynchronous loop. Select_trigger implements thread-safe and
	practical loginfo interfaces:
		
		select_trigger_log (data, info=None)
		
	to log information, and
		
		select_trigger_traceback ()
		
	to log traceback asynchronously from a distinct thread."""

	select_trigger = None

	def __init__ (self):
                "maybe open a new Trigger, increase its reference count"
		if self.select_trigger == None:
			Select_trigger.select_trigger = Trigger ()
		self.select_trigger.select_triggers += 1
		
	def __repr__ (self):
		return 'select-trigger id="%x"' % id (self)
		
	def select_trigger_log (self, data, info=None):
		"log asynchronously via the select trigger"
		self.select_trigger ((self.log, (data, info)))
		
	def select_trigger_traceback (self):
		"return a compact traceback tuple and log asynchronously"
		ctb = prompt.compact_traceback ()
		self.select_trigger ((
                        self.loginfo_log,
			loginfo.traceback_encode (ctb)
			))
		return ctb

	def finalization (self, finalized):
		"decrease the Trigger's reference count, maybe close it"
                trigger = self.select_trigger
		trigger.select_triggers -= 1
		if trigger.select_triggers == 0:
			trigger ((trigger.handle_close, ()))
			Select_trigger.select_trigger = None
		self.select_trigger = None