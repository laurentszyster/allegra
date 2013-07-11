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

"http://laurentszyster.be/blog/synchronized/"

import collections, subprocess

from allegra import loginfo, finalization, thread_loop 


# File producer and collector

def sync_open (self, filename, mode, bufsize):
        try:
                self.sync_file = open (filename, mode, bufsize)
        except:
                self.select_trigger ((self.async_close, ('eo', )))
        else:
                self.select_trigger ((self.async_open, (mode, )))
        
def sync_write (self, data):
        try:
                self.sync_file.write (data)
        except:
                self.select_trigger ((self.async_close, ('ew', )))
        
def sync_read (self):
        try:
                data = self.sync_file.read (self.sync_buffer)
        except:
                self.select_trigger ((self.async_close, ('er', )))
        else:
                if data:
                        self.select_trigger ((self.async_read, (data, )))
                else:
                        sync_close (self, 'r')
        
def sync_close (self, mode):
        try:
                self.sync_file.close ()
        except:
                self.select_trigger ((self.async_close, ('ec', )))
        else:
                self.select_trigger ((self.async_close, (mode, )))
        self.sync_file = None
        

class File_producer (object):

        synchronizer = None
        synchronizer_size = 2
        
        async_buffers = ()
        async_closed = False

        def __init__ (self, filename, mode='rb', bufsize=1<<14):
                assert (
                        type (filename) == str and
                        mode.startswith ('r') and 
                        (0 < len (mode) < 3) and
                        buffer > 0
                        )
                self.sync_buffer = bufsize
                self.async_buffers = collections.deque([])
                thread_loop.synchronize (self)
                self.synchronized ((
                        sync_open, (self, filename, mode, bufsize)
                        ))

        def __repr__ (self):
                return 'synchronized-file-producer id="%x"' % id (self)
                        
        def more (self):
                try:
                        return self.async_buffers.popleft ()
                        
                except:
                        return ''
                        
        def producer_stalled (self):
                return not (
                        self.async_closed or len (self.async_buffers) > 0
                        )
                        
        def async_open (self, mode):
                self.synchronized ((sync_read, (self, )))
        
        def async_read (self, data):
                self.async_buffers.append (data)
                self.synchronized ((sync_read, (self, )))
                
        def async_close (self, mode):
                self.async_closed = True
                thread_loop.desynchronize (self)
                                

class File_collector (object):

        synchronizer = None
        synchronizer_size = 2
        
        collector_is_simple = True
        
        async_closed = False

        def __init__ (self, filename, mode='wb', bufsize=-1):
                assert (
                        type (filename) == str and
                        not mode.startswith ('r') and 
                        (0 < len (mode) < 3)
                        )
                thread_loop.synchronize (self)
                self.synchronized ((
                        sync_open, (self, filename, mode, bufsize)
                        ))

        def __repr__ (self):
                return 'synchronized-file-collector id="%x"' % id (self)
                
        def collect_incoming_data (self, data):
                self.synchronized ((sync_write, (self, data,)))
                
        def found_terminator (self):
                self.synchronized ((sync_close, (self, 'w', )))
                return True

        def async_open (self, mode): pass
        
        def async_close (self, mode):
                self.async_closed = True
                thread_loop.desynchronize (self)


# Subprocess reactor

def sync_popen (self, args):
        try:
                self.subprocess = subprocess.Popen (*args)
        except Exception, error:
                self.select_trigger ((self.async_except, (error, )))
        else:
                self.select_trigger ((self.async_popen, ()))

def sync_stdin (self, data):
        try:
                self.subprocess.stdin.write (data)
        except Exception, error:
                self.select_trigger ((self.async_except, (error, )))
                
def sync_stdout (self):
        exit = self.subprocess.poll ()
        if exit != None:
                sync_wait (self)
                return
        
        try:
                data = self.subprocess.stdout.read (self.sync_buffer)
        except Exception, error:
                self.select_trigger ((self.async_except, (error, )))
        else:
                if data:
                        self.select_trigger ((self.async_stdout, (data, )))
                else:
                        sync_wait (self)
        
def sync_wait (self):
        if self.subprocess == None:
                self.select_trigger ((self.async_return, (None, )))
                return
                
        sub = self.subprocess
        self.subprocess = None
        sub.stdin.close ()
        sub.stdout.close ()
        if sub.stderr:
                sub.stderr.close ()
        self.select_trigger ((self.async_return, (sub.wait (), )))


class Popen_producer (object):
        
        synchronizer = None
        synchronizer_size = 2

        subprocess = async_code = None
        sync_buffer = 1<<16
        
        def __init__ (self):
                self.async_buffers = collections.deque([])
                thread_loop.synchronize (self)
                
        def more (self):
                try:
                        return self.async_buffers.popleft ()
                        
                except:
                        return ''
        
        def producer_stalled (self):
                return (
                        self.async_code == None and
                        len (self.async_buffers) == 0
                        )

        def async_popen (self):
                self.synchronized ((sync_stdout, (self, )))

        def async_stdout (self, data):
                self.async_buffers.append (data)
                self.synchronized ((sync_stdout, (self, )))
                
        def async_stderr (self, data):
                assert None == loginfo.log (
                        'async_error', 'not implemented'
                        )
                
        def async_except (self, error):
                assert None == loginfo.log (str (error), 'debug')
                sync_wait (self)
                
        def async_return (self, code):
                self.async_code = code
                thread_loop.desynchronize (self)
                assert None == loginfo.log ('exit (%r)' % code, 'debug')


def popen_producer (
        args, bufsize=0, executable=None, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        preexec_fn=None, close_fds=False, 
        shell=False, cwd=None, env=None, 
        universal_newlines=False, startupinfo=None, 
        creationflags=0
        ):
        assert (
                stdin == subprocess.PIPE and 
                stdout == subprocess.PIPE and
                stderr in (subprocess.PIPE, subprocess.STDOUT)
                )
        sp = Popen_producer ()
        sp.synchronized ((sync_popen, (sp, (
                args, bufsize, executable, stdin, stdout, stderr,
                preexec_fn, close_fds, shell, cwd, env, 
                universal_newlines, startupinfo, creationflags
                ))))
        return sp
        

class Popen_collector (object):
        
        synchronizer = None
        synchronizer_size = 2

        collector_is_simple = True

        subprocess = async_code = None
        
        def __init__ (self):
                thread_loop.synchronize (self)
                
        def collect_incoming_data (self, data):
                self.synchronized ((sync_stdin, (self, data,)))
                
        def found_terminator (self):
                self.synchronized ((sync_wait, (self, )))
                return True
        
        def async_popen (self):
                assert None == loginfo.log ('async_popen', 'debug')

        def async_stderr (self, data):
                assert None == loginfo.log (
                        'async_error', 'not implemented'
                        )
                
        def async_except (self, error):
                assert None == loginfo.log (str (error), 'debug')
                sync_wait (self)
                
        def async_return (self, code):
                self.async_code = code
                thread_loop.desynchronize (self)
                assert None == loginfo.log ('%r' % code, 'debug')


def popen_collector (
        args, bufsize=0, executable=None, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        preexec_fn=None, close_fds=False, 
        shell=False, cwd=None, env=None, 
        universal_newlines=False, startupinfo=None, 
        creationflags=0
        ):
        assert (
                stdin == subprocess.PIPE and 
                stdout == subprocess.PIPE and
                stderr in (subprocess.PIPE, subprocess.STDOUT)
                )
        sc = Popen_collector ()
        sc.synchronized ((sync_popen, (sc, (
                args, bufsize, executable, stdin, stdout, stderr,
                preexec_fn, close_fds, shell, cwd, env, 
                universal_newlines, startupinfo, creationflags
                ))))
        return sc


class Popen_reactor (finalization.Finalization):
        
        def __init__ (
                self, args, 
                bufsize=0, executable=None, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                preexec_fn=None, close_fds=False, 
                shell=False, cwd=None, env=None, 
                universal_newlines=False, startupinfo=None, 
                creationflags=0
                ):
                assert (
                        stdin == subprocess.PIPE and 
                        stdout == subprocess.PIPE and
                        stderr in (subprocess.PIPE, subprocess.STDOUT)
                        )
                self.collector = Popen_collector ()
                self.producer = Popen_producer ()
                self.collector.async_popen = self.async_popen
                self.collector.found_terminator = self.found_terminator
                self.producer.async_return = self.async_return
                self.collector.synchronized ((sync_popen, (self.collector, (
                        args, bufsize, executable, stdin, stdout, stderr,
                        preexec_fn, close_fds, shell, cwd, env, 
                        universal_newlines, startupinfo, creationflags
                        ))))
                
        def async_popen (self):
                self.producer.subprocess = self.collector.subprocess
                self.producer.synchronized ((
                        sync_stdout, (self.producer, )
                        ))
                self.collector.async_popen = None
                
        def found_terminator (self):
                self.collector.found_terminator = None
        
        def async_return (self, code):
                scin = self.collector
                spout = self.producer
                scin.async_code = spout.async_code = code
                self.producer = self.collector = None
                spout.async_return = None
                thread_loop.desynchronize (scin)
                thread_loop.desynchronize (spout)
                assert None == loginfo.log ('%r' % code, 'debug')
        