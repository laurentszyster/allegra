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
#

"http://laurentszyster.be/blog/reactor/"


class Buffer (object):

	"a buffer reactor, usefull for asynchronous/synchronous proxy"

        collector_is_simple = True
        buffer_reactor_complete = False

        def __init__ (self):
                self.buffers = []
                self.collect_incoming_data = self.buffers.append
                
	def found_terminator (self):
		self.buffer_reactor_complete = True
                return True

        def more (self):
                try:
                        return self.buffers.pop (0)
                    
                except IndexError:
                        return ''

        def producer_stalled (self):
                return (
			len (self.buffers) == 0 and
			self.buffer_reactor_complete == False
                        )

# The simplest reactor implementation: a pipe