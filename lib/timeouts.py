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

"http://laurentszyster.be/blog/timeouts/"

import time, collections

from allegra import async_loop


class Timeouts (object):
	
	def __init__ (self, period, precision=None):
		# self.timeouts_timeout = timeout
		self.timeouts_period = max (period, async_loop.precision)
		self.timeouts_precision = precision or async_loop.precision
		self.timeouts_deque = collections.deque ()
                        
        def timeouts_push (self, reference):
                when = time.time ()
                if not self.timeouts_deque:
                        self.timeouts_start (when)
		self.timeouts_deque.append ((when, reference))
		return reference
	
        def timeouts_start (self, when):
                async_loop.schedule (
                        when + self.timeouts_precision, self.timeouts_poll
                        )
                
	def timeouts_poll (self, now):
		then = now - self.timeouts_precision - self.timeouts_period 
		while self.timeouts_deque:
			when, reference = self.timeouts_deque[0]
			if  when < then:
				self.timeouts_deque.popleft ()
				self.timeouts_timeout (reference)
			else:
				break
				
                if self.timeouts_deque:
                        return (
                                now + self.timeouts_precision, 
                                self.timeouts_poll
                                )

                self.timeouts_stop ()

	def timeouts_stop (self):
                pass # self.timeouts_timeout = None
	

# The first, simplest and probably most interesting application of Timeouts

def cached (cache, timeout, precision):
        def timedout (reference):
                try:
                        del cache[reference]
                except KeyError:
                        pass
        
        t = Timeouts (timeout, precision)
        t.timeouts_timeout = timedout
        def push (key, value):
                cache[key] = value
                t.timeouts_push (key)
                
        return push

# push, stop = timeouts.cached ({}, 60, 6)
# ...
# push (key, value)
# ...
# stop ()
        
# Note about this implementation	
#
# Time out
#
# In order to scale up and handle very large number of timeouts scheduled
# asynchronously at fixed intervals, this module provides a simple deque 
# interface that for a fifo of timeout events to poll from.
#
# Polling a timeouts queue should be scheduled recurrently at more or less
# precise intervals depending on the volume expected and the time it takes
# to handle each timeout. Your mileage may vary, but this design will scale
# up in the case of long intervals, when for each time poll only a few first 
# events at the left of the deque have timed-out.
#
# The timouts interface is applied by pns_udp to manage the 3 second timeout
# set on each statement relayed or routed by a PNS/UDP circle. There might
# be other applications, RTP protocols for instance.