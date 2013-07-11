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

"http://laurentszyster.be/blog/netstring/"


class NetstringsError (Exception): pass


def encode (strings):
        "encode an sequence of 8-bit byte strings as netstrings"
        return ''.join (['%d:%s,' % (len (s), s) for s in strings])

        
def decode (buffer):
	"decode the netstrings found in the buffer, trunk garbage"
	size = len (buffer)
	prev = 0
	while prev < size:
		pos = buffer.find (':', prev)
		if pos < 1:
			break
			
		try:
			next = pos + int (buffer[prev:pos]) + 1
		except:
			break
	
		if next >= size:
			break
		
		if buffer[next] == ',':
			yield buffer[pos+1:next]

		else:
			break
			
		prev = next + 1


def validate (buffer, length):
        "decode the netstrings, but keep garbage and fit to size"
        size = len (buffer)
        prev = 0
        while prev < size and length:
                pos = buffer.find (':', prev)
                if pos < 1:
                        if prev == 0:
                                raise StopIteration # not a netstring!
                        
                        break
                        
                try:
                        next = pos + int (buffer[prev:pos]) + 1
                except:
                        break
        
                if next >= size:
                        break
                
                if buffer[next] == ',':
                        length -= 1
                        yield buffer[pos+1:next]

                else:
                        break
                        
                prev = next + 1

        if length:
                length -= 1
                yield buffer[max (prev, pos+1):]
        
                while length:
                        length -= 1
                        yield ''
                        


def outline (encoded, format, indent):
	"recursively format nested netstrings as a CRLF outline"
	n = tuple (decode (encoded))
	if len (n) > 0:
		return ''.join ((outline (
			e, indent + format, indent
			) for e in n))
			
	return format % encoded


def netstrings (instance):
	"encode a tree of instances as nested netstrings"
	t = type (instance)
	if t == str:
		return instance
		
	if t in (tuple, list, set, frozenset):
		return encode ((netstrings (i) for i in instance))
                
        if t == dict:
                return encode ((netstrings (i) for i in instance.items ()))

	try:
		return '%s' % instance
		
	except:
		return '%r' % instance
		

def netlist (encoded):
	"return a list of strings or [encoded] if no netstrings found"
	return list (decode (encoded)) or [encoded]


def nettree (encoded):
	"decode the nested encoded strings in a tree of lists"
	leaves = [nettree (s) for s in decode (encoded)]
	if len (leaves) > 0:
		return leaves
		
	return encoded


def netlines (encoded, format='%s\n', indent='  '):
	"beautify a netstring as an outline ready to log"
	n = tuple (decode (encoded))
	if len (n) > 0:
		return format % ''.join ((outline (
			e, format, indent
			) for e in n))
			
	return format % encoded


def netoutline (encoded, indent=''):
        "recursively format nested netstrings as an outline with length"
        n = tuple (decode (encoded))
        if len (n) > 0:
                return '%s%d:\n%s%s,\n' % (
                        indent, len (encoded), ''.join ((netoutline (
                                e, indent + '  '
                                ) for e in n)), indent)
        
        return '%s%d:%s,\n' % (indent, len (encoded), encoded)


def netpipe (more, BUFFER_MAX=0):
	"""A practical netstrings pipe generator
	
	Decode the stream of netstrings produced by more (), raise 
	a NetstringsError exception on protocol failure or StopIteration
	when the producer is exhausted.
	
	If specified, the BUFFER_MAX size must be more than twice as
	big as the largest netstring piped through (although netstrings
	strictly smaller than BUFFER_MAX may pass through without raising
	an exception).
	"""
	buffer = more ()
	while buffer:
		pos = buffer.find (':')
		if pos < 0:
			raise NetstringsError, '1 not a netstring' 
		try:
			next = pos + int (buffer[:pos]) + 1
		except:
			raise NetstringsError, '2 not a valid length'
	
		if 0 < BUFFER_MAX < next:
			raise (
				NetstringsError, 
				'4 buffer overflow (%d bytes)' % BUFFER_MAX
				)
			
		while next >= len (buffer):
			data = more ()
			if data:
				buffer += data
			else:
				raise NetstringsError, '5 end of pipe'
		
		if buffer[next] == ',':
			yield buffer[pos+1:next]

		else:
			raise NetstringsError, '3 missing coma'

		buffer = buffer[next+1:]
		if buffer == '' or buffer.isdigit ():
			buffer += more ()

	#
	# Note also that the first call to more must return at least the
	# encoded length of the first netstring, which practically is (or
	# should be) allways the case (for instance, piping in a netstring
	# sequence from a file will be done by blocks of pages, typically
	# between 512 and 4096 bytes, maybe more certainly not less).


if __name__ == '__main__':
        import sys
        assert None == sys.stderr.write (
                'Allegra Netstrings'
                ' - Copyright 2005 Laurent A.V. Szyster'
                ' | Copyleft GPL 2.0\n\n'
                )
        if len (sys.argv) > 1:
        	command = sys.argv[1]
 	else:
		command = 'outline'
 	if command in ('outline', 'decode'):
 		if len (sys.argv) > 2:
	 		if len (sys.argv) > 3:
				try:
					buffer_max = int (sys.argv[3])
				except:
					sys.stderr.write (
						'3 invalid buffer max\n'
						)
					sys.exit (3)
					
			else:
				buffer_max = 0
 			try:
				buffer_more = int (sys.argv[2])
			except:
				sys.stderr.write ('2 invalid buffer size\n')
				sys.exit (2)
				
		else:
			buffer_max = 0
	 		buffer_more = 4096
		def more ():
			return sys.stdin.read (buffer_more)
                count = 0
                try:
        		if command == 'outline':
                                write = sys.stdout.write
        			for n in netpipe (more, buffer_max):
        				write (netlines (n))
                                        count += 1
        		else:
        			for n in netpipe (more, buffer_max):
        				count += 1
                finally:
                        assert None == sys.stderr.write ('%d' % count)
	elif command == 'encode':
                write = sys.stdout.write 
		for line in sys.stdin.xreadlines ():
			write ('%d:%s,' % (len (line)-1, line[:-1]))
	else:
		sys.stderr.write ('1 invalid command\n')
		sys.exit (1)
		
	sys.exit (0)