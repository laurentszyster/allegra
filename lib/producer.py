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

"http://laurentszyster.be/blog/producer/"


import types


class File (object):
        
        "producer wrapper for file[-like] objects"

        def __init__ (self, file, chunk=1<<14): # 16KB buffer
                self.file = file
                self.chunk = chunk

        def more (self):
                return self.file.read (self.chunk)

        def producer_stalled (self):
                return False
        

class Simple (object):
        
        "scanning producer for a large string"

        def __init__ (self, data, chunk=1<<14): # 16KB buffer
                lb = len (data)
                self.content_length = lambda: lb
                self.more = self.produce (data, chunk).next

        def produce (self, data, chunk):
                lb = len (data)
                start = 0
                while start < lb:
                        end = start + chunk
                        yield data[start:end]

                        start = end
                del data, self.content_length, self.more
                yield ''
        
        def producer_stalled (self):
                return False


class Stalled_generator (object):
        
        # the simplest stallable generator, a usefull construct for any
        # generator based producer that is set as a finalization or a 
        # handler of diverse asynchronous or synchronized callback ...
        
        def __call__ (self, *args):
                self.generator = iter ((
                        'Stalled_generator.__call__ not implemented', 
                        ))
        
        generator = None
        
        def more (self):
                try:
                        return self.generator.next ()
                
                except StopIteration:
                        return ''
        
        def producer_stalled (self):
                return self.generator == None
        

class Composite (object):
	
	# This is a more "modern" composite producer than the original
	# one, with support for stalled producers and generators. it is the
	# bread & butter of Allegra's PRESTo! with the Buffer.
	
        def __init__ (self, head, body, glob=1<<14): # 16KB globber
        	assert (
        		type (head) == types.StringType and 
        		type (body) == types.GeneratorType
        		)
        	self.current = head
                self.generator = body
                self.glob = glob
                
        def more (self):
        	if self.current == '':
        		return ''
        		
        	buffer = ''
        	limit = self.glob
        	while True:
	        	if type (self.current) == str:
	        		buffer += self.current
	        		try:
	  				self.current = self.generator.next ()
		  		except StopIteration:
		  			self.current = ''
		  			break
		  		
		  		if len (buffer) > limit:
		  			break
		  			
			elif self.current.producer_stalled ():
				assert buffer != '' # watch this!
				break
				
			else:
				data = self.current.more ()
				if data:
					buffer += data
					if len (buffer) > limit:
						break
					
					else:
						continue
						
	        		try:
	  				self.current = self.generator.next ()
		  		except StopIteration:
		  			self.current = ''
		  			break
		  		
		return buffer
                
	def producer_stalled (self):
		try:
			return self.current.producer_stalled ()
			
		except:
			return False
			
	# Note that this class also makes the original Medusa's lines, buffer 
	# and globbing producer redundant. What this class does it to glob
	# as much strings as possible from a MIME like data structure:
	#
	#	head = 'string'
	#	body = (generator of 'string' or producer ())
	#
        # It's a practical producer for asynchronous REST responses composed
        # of simple strings and maybe-stalling producers. The overhead of
        # another loop buys globbing and helps the peer fill its channel's
        # buffers more efficiently for TCP/IP.


class Tee (object):
        
        def __init__ (self, producer):
                self.index = -1
                self.producer = producer
                try:
                        self.buffers = producer.tee_buffers 
                except AttributeError:
                        self.buffers = producer.tee_buffers = []
                
        def more (self):
                self.index += 1
                try:
                        return self.buffers[self.index]
                
                except IndexError:
                        data = self.producer.more ()
                        self.buffers.append (data)
                        return data
                
        def producer_stalled (self):
                if self.index + 1 < len (self.buffers):
                        return False
                
                return self.producer.producer_stalled ()
