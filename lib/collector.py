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

"http://laurentszyster.be/blog/collector/"


from allegra import async_chat, loginfo


class Null (object):

        # collect data to /dev/null

        collector_is_simple = True

        def collect_incoming_data (self, data):
                return

        def found_terminator (self):
                return True


DEVNULL = Null ()


class Loginfo (object):
        
        # collect data to loginfo
        
        collector_is_simple = True

        def __init__ (self, info=None):
                self.info = info
        
        def collect_incoming_data (self, data):
                loginfo.log (data, self.info)
                
        def found_terminator (self):
                return True # final!


LOGINFO = Loginfo ()
                

class File (object):
        
        collector_is_simple = True
        
        def __init__ (self, file):
                self.file = file
                self.collect_incoming_data = self.file.write

        def found_terminator (self):
                self.file.close ()
                self.collect_incoming_data = None
                return True
                
                
def devnull (data): pass
                
class Limited (object):
        
        collector_is_simple = True
        
        def __init__ (self, limit):
                self.data = ''
                self.limit = limit

        def collect_incoming_data (self, data):
                self.limit -= len (data)
                if self.limit > 0:
                        self.data += data
                else:
                        self.collect_incoming_data = devnull
                        # 
                        # just don't do anything after the limit, not even
                        # testing for it ;-)

        def found_terminator (self):
                return True
                

class Codec_decoder (object):
        
        # Decode collected data using the codecs' decode interface:
        #
        #        import codecs
        #        Codec_decoder (collector, codecs.lookup ('zlib')[1])
        #
        # Note that the decode function *must* decode byte strings, not
        # UNICODE strings.
        
        collector_is_simple = True
        
        def __init__ (self, collector, decode):
                assert collector.collector_is_simple
                self.collector = collector
                self.decode = decode
                self.buffer = ''
        
        def collect_incoming_data (self, data):
                if self.buffer:
                        decoded, consumed = self.decode (self.buffer + data)
                        consumed -= len (self.buffer)
                else:
                        decoded, consumed = self.decode (data)
                self.collector.collect_incoming_data (decoded)
                if consumed < len (data) + 1:
                        self.buffer = data[consumed:]
                        
        def found_terminator (self, data):
                if self.buffer:
                        decoded, consumed = self.decode (self.buffer)
                        if decoded:
                                self.collector.collect_incoming_data (decoded)
                return self.collector.found_terminator ()
       

class Padded_decoder (object):
        
        # Collect padded blocks to decode, for instance:
        #
        #        import base64
        #        Padded_decoder (collector, 20, base64.b64decode)
        #
        # because padding does matter to the base binascii implementation,
        # and is not handled by the codecs module, a shame when a large
        # XML string is encoded in base64 and should be decoded and parsed
        # asynchronously. Padding is also probably a requirement from block
        # cypher protocols and the likes.
        
        collector_is_simple = True
        
        def __init__ (self, collector, padding, decode):
                assert collector.collector_is_simple
                self.collector = collector
                self.padding = padding
                self.decode = decode
                self.buffer = ''
        
        def collect_incoming_data (self, data):
                lb = len (self.buffer) + len (data) 
                if lb < self.padding:
                        self.buffer += data
                        return

                tail = lb % self.padding
                if self.buffer:
                        if tail:
                                self.buffer = data[-tail:]
                                self.collector.collect_incoming_data (
                                        self.decode (
                                                self.buffer + data[:-tail]
                                                )
                                        )
                        else:
                                self.collector.collect_incoming_data (
                                        self.decode (self.buffer + data)
                                        )
                elif tail:
                        self.buffer = data[-tail:]
                        self.collector.collect_incoming_data (
                                self.decode (data[:-tail])
                                )
                else:
                        self.collector.collect_incoming_data (
                                self.decode (data)
                                )
        
        def found_terminator (self):
                if self.buffer:
                        self.collector.collect_incoming_data (
                                self.decode (self.buffer)
                                )
                        self.buffer = ''
                return self.collector.found_terminator ()
        
        
class Simple (object):

        collector_is_simple = True
        terminator = None
        buffer = ''

        def get_terminator (self):
                return self.terminator

        def set_terminator (self, terminator):
                self.terminator = terminator

        def collect_incoming_data (self, data):
                self.buffer = async_chat.collect_chat (
                        self.collector, self.buffer + data
                        )
                        
        def found_terminator (self):
                if self.buffer:
                        async_chat.collect_chat (self.collector, self.buffer)
                return True # allways final


def bind_simple (cin, cout):
        "bind to a simple collector until found_terminator is True"
        def found_terminator ():
                if cout.found_terminator ():
                        del (
                                cin.collect_incoming_data,
                                cin.found_terminator
                                )
                        return cin.found_terminator ()
                
                return False

        cin.collect_incoming_data = cout.collect_incoming_data
        cin.found_terminator = found_terminator
        return cin

def bind_complex (cin, cout):
        "bind to a complex collector until found_terminator is True"
        cout.set_terminator = cin.set_terminator
        cout.get_terminator = cin.get_terminator
        cout.collector = cin
        cin.set_terminator (cout.get_terminator ())
        cin.collect_incoming_data = cout.collect_incoming_data
        def found_terminator ():
                if cout.found_terminator ():
                        del (
                                cout.set_terminator,
                                cout.get_terminator,
                                cout.collector,
                                cin.collect_incoming_data,
                                cin.found_terminator
                                )
                        return cin.found_terminator ()
                
                return False
        
        cin.found_terminator = found_terminator
        return cin

def bind (cin, cout):
        "bind a complex to a collector until found_terminator is True"
        assert not cin.collector_is_simple
        if cout.collector_is_simple:
                return bind_simple (cin, cout)

        return bind_complex (cin, cout)


def simplify (cin, cout):
        couple = Simple ()
        bind_complex (couple, cout)
        return bind_simple (cin, couple)

def simple (collected):
        return bind_simple (Simple (), collected)        