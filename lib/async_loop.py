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

"http://laurentszyster.be/blog/async_loop/"

import gc, select, errno, time, collections, heapq

from allegra import loginfo


Exit = KeyboardInterrupt


# Poll I/O

def _io_select (map, timeout, limit):
        "poll for I/O a limited number of writable/readable dispatchers"
        r = []
        w = []
        concurrent = map.items ()
        rest = limit - len (concurrent)
        if rest < 0:
                concurrent = concurrent[:limit]
        else:
                rest = 0
        for fd, dispatcher in concurrent:
                if dispatcher.readable ():
                        r.append (fd)
                if dispatcher.writable ():
                        w.append (fd)
        if len (r) + len (w) == 0:
                time.sleep (timeout)
                return limit - rest, 0

        try:
                r, w, e = select.select (r, w, [], timeout)
        except select.error, err:
                if err[0] != errno.EINTR:
                    raise
                    
                else:
                    return limit - rest, 0

        for fd in r:
                try:
                        dispatcher = map[fd]
                except KeyError:
                        continue

                try:
                        dispatcher.handle_read_event ()
                except Exit:
                        raise
                        
                except:
                        dispatcher.handle_error ()
        for fd in w:
                try:
                        dispatcher = map[fd]
                except KeyError:
                        continue

                try:
                        dispatcher.handle_write_event ()
                except Exit:
                        raise 
                        
                except:
                        dispatcher.handle_error ()
        return limit - rest, len (r) + len (w)
        #
        # note that the number of distinct active dispatchers may actually
        # be lower than the one reported: to get an exact cound would
        # require to use sets, something like: len (set (r) + set (w))

def _io_poll (map, timeout, limit):
        "poll for I/O a limited number of writable/readable dispatchers"
        timeout = int (timeout*1000)
        pollster = select.poll ()
        R = select.POLLIN | select.POLLPRI
        W = select.POLLOUT
        RW = R | W
        concurrent = map.items ()
        rest = limit - len (concurrent)
        if rest < 0:
                concurrent = concurrent[:limit]
        else:
                rest = 0
        for fd, dispatcher in concurrent:
                if dispatcher.readable ():
                        if dispatcher.writable ():
                                pollster.register (fd, RW)
                        else:
                                pollster.register (fd, R)
                elif dispatcher.writable ():
                        pollster.register (fd, W)
        try:
                p = pollster.poll (timeout)
        except select.error, err:
                if err[0] != errno.EINTR:
                        raise
                        
        else:
                for fd, flags in p:
                        try:
                                dispatcher = map[fd]
                        except KeyError:
                                continue
        
                        try:
                                if flags & R:
                                        dispatcher.handle_read_event ()
                                if flags & W:
                                        dispatcher.handle_write_event ()
                        except Exit:
                                raise 
                                
                        except:
                                dispatcher.handle_error()
        return limit - rest, len (p)


# select the best I/O poll function available for this system

if hasattr (select, 'poll'):
	_io = _io_poll
else:
	_io = _io_select


# Poll Memory (Finalizations, ie: CPython __del__ decoupled)

_finalized = collections.deque ()

def _finalize ():
	"call all finalizations queued"
        while True:
                try:
                        finalized = _finalized.popleft ()
                except IndexError:
                        break
                       
                try:
                        finalized.finalization = finalized.finalization (
                               finalized
                               ) # finalize and maybe continue ...
                except Exit:
                        finalized.finalization = None
                        raise
                
                except:
                        finalized.finalization = None
                        loginfo.traceback () # log exception
        
	
# Poll Time (Scheduled Events)

precision = 0.1

_scheduled = []

def _clock ():
	"call all events scheduled before now, maybe recurr in the future"
	now = time.time ()
        future = now + precision
	while _scheduled:
		# get the next defered ...
		event = heapq.heappop (_scheduled)
		if event[0] > now:
			heapq.heappush (_scheduled, event)
			break  # ... nothing to defer now.

		try:
			# ... do defer and ...
			continued = event[1] (event[0])
                except Exit:
                        raise
                
		except:
			loginfo.traceback ()
		else:
			if continued != None:
                                # ... maybe recurr in the future
                                if continued[0] < future:
                                        continued = (future, continued[1])
				heapq.heappush (_scheduled, continued) 


# Poll Signals (Exceptions Handler)

_catchers = []

def _catched ():
        "call async_loop.Exit exception catchers"
        assert None == loginfo.log ('async_catch', 'debug')
        if _catchers:
                for catcher in tuple (_catchers):
                        if catcher ():
                                _catchers.remove (catcher)
                return True
        
        if __debug__:
                for dispatcher in _dispatched.values ():
                        loginfo.log (
                                '%r' % dispatcher, 'undispatched'
                                )
                for event in _scheduled:
                        loginfo.log (
                                '%r' % (event, ), 'unscheduled'
                                )
                for finalized in _finalized:
                        loginfo.log (
                                '%r' % (finalized, ), 'unfinalized'
                                )
        return False


# Application Programming Interfaces

def schedule (when, scheduled):
        "schedule a call to scheduled after when"
        heapq.heappush (_scheduled, (when, scheduled))        
        

def catch (catcher):
        "register an catcher for the Exit exception"
        _catchers.append (catcher)


concurrency = 512

_dispatched = {}

def dispatch ():
        "dispatch I/O, time and finalization events"
        assert None == loginfo.log ('async_dispatch_start', 'debug')
        while _dispatched or _scheduled or _finalized or gc.collect () > 0:
                try:
                        _io (_dispatched, precision, concurrency)
                        _clock ()
                        _finalize ()
                except Exit:
                        if not _catched ():
                                break
                
                except:
                        loginfo.traceback ()
        
        assert None == loginfo.log ('async_dispatch_stop', 'debug')
   
   
def io_meter (loop, when=None):
        "decorate the loop module's I/O poll function with meters, log info"
        loop._io_when = when or time.time ()
        loop._io_run = 0
        loop._io_load = loop._io_concurrency = loop._io_activity = 0.0
        def _io_metering (map, timeout, limit):
                loop._io_run += 1
                dispatched = len (loop._dispatched)
                concurrent, polled = _io (map, timeout, limit)
                if concurrent > 0:
                        loop._io_activity += float (active) / concurrent
                        concurrent = float (concurrent)
                        loop._io_load += concurrent / limit
                        loop._io_concurrency += concurrent / dispatched

        loop._io_metered = loop._io
        loop._io = _io_metering
        loginfo.log ('io-metered', 'info')
        
def io_meters (loop):
        "return statistics about a metered I/O loop"
        return (
                loop._io_when, loop._io_run,
                loop._io_run / (time.time () - loop._io_when),
                loop._io_load / loop._io_run,
                loop._io_concurrency / loop._io_run,
                loop._io_activity / loop._io_run
                )

def io_unmeter (loop):
        "log meter statistics and remove the metering decoration"
        meters = io_meters (loop)
        loginfo.log (
                'io-unmetered'
                ' seconds="%f" run="%d"'
                ' rps="%f" load="%f"'
                ' concurrency="%f" activity="%f"' % meters, 'info'
                )
        del (
                loop._io_when, loop._io_run, 
                loop._io_load, _io_concurrency, loop._io_activity
                )
        loop._io = loop._io_metered
        return meters