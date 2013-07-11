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

"http://laurentszyster.be/blog/loginfo/"

import sys

from allegra import netstring, prompt


def _write_maybe_flush (file):
        assert hasattr (file, 'write')
	if hasattr (file, 'flush'):
                def write (data):
                        file.write (data)
                        file.flush ()
                        return 
                
		return write

	return file.write


class Logger (object):

	"Loginfo's log dispatcher implementation"
	
	def __init__ (self):
                self.loginfo_stdout = _write_maybe_flush (sys.stdout)
                self.loginfo_stderr = _write_maybe_flush (sys.stderr)
		self.loginfo_categories = {}

	def loginfo_netstrings (self, data, info=None):
		"log netstrings to STDOUT, a category handler or STDERR"
                assert type (data) == str
		if info == None:
			self.loginfo_stdout ('%d:%s,' % (len (data), data))
		elif self.loginfo_categories.has_key (info):
			self.loginfo_categories[info] (
				'%d:%s,' % (len (data), data)
				)
		else:
                        assert type (info) == str
			encoded = netstring.encode ((info, data))
			self.loginfo_stderr (
				'%d:%s,' % (len (encoded), encoded)
				)

	def loginfo_netlines (self, data, info=None):
		"log netoutlines to STDOUT, a category handler or STDERR"
                assert type (data) == str
		if info == None:
			self.loginfo_stdout (netstring.netlines (data))
		elif self.loginfo_categories.has_key (info):
			self.loginfo_categories[info] (
				netstring.netlines (data)
				)
		else:
			assert type (info) == str
			self.loginfo_stderr (netstring.netlines (
				netstring.encode ((info, data))
				))

	if __debug__:
		log = loginfo_netlines
	else:
		log = loginfo_netstrings


# the facility instance and module interfaces

logger = Logger ()

def log (*args):
        logger.log (*args)


def compact_traceback (ctb):
	"encode a compact traceback tuple as netstrings"
 	return netstring.encode ((
                ctb[0], 
 		netstring.encode ([' | '.join (x) for x in ctb[2]]),
                ctb[1]
 		)), 'traceback'
                 
def classic_traceback (ctb=None):
        return netstring.encode ((
                netstring.encode ([
                        'File "%s", line %s, in %s' % (
                                tb[0] or '<string>', tb[2], tb[1]
                                )
                        for tb in ctb[2]
                        ]), '%s: %s' % ctb[:2]
                )), 'Traceback (most recent call last):'

traceback_encode = compact_traceback
        
def traceback (ctb=None):
        "return a compact traceback and log it in the 'traceback' category"
        if ctb == None:
                ctb = prompt.compact_traceback ()
        logger.log (*traceback_encode (ctb))
        return ctb


# redirection of all Python standard outputs to the logger

class _STDOUT (object):

        def write (self, line):
                logger.log (line)
        
sys.stdout = _STDOUT ()

def _displayhook (value):
        if value != None:
                logger.log ('%r' % (value,))
        
sys.displayhook = _displayhook
        
class _STDERR (object):

        def write (self, line):
                logger.log (line, 'stderr')
        
def _excepthook (*exc_info):
        traceback (prompt.compact_traceback (exc_info))

sys.excepthook = _excepthook


# a class interface to mix in

class Loginfo (object):

	loginfo_logger = logger
	
	def __repr__ (self):
		return '%s id="%x"' % (
			self.__class__.__name__, id (self)
			)

	def loginfo_log (self, data, info=None):
		"""log a message with this instance's __repr__ and an 
		optional category"""
		self.loginfo_logger.log (netstring.encode ((
			'%r' % self, '%s' % data
			)), info)

	log = loginfo_log

	def loginfo_null (self, data, info=None):
                "drop the message to log"
                pass
                
        def loginfo_logging (self):
        	"return True if the instance is logging"
        	return self.log != self.loginfo_null

	def loginfo_toggle (self, logging=None):
		"toggle logging on/off for this instance"
		if logging == None:
			if self.log == self.loginfo_null:
				try:
					del self.log
				except:
					self.log = self.loginfo_log
			else:
				try:
					del self.log
				except:
					self.log = self.loginfo_null
			return self.log != self.loginfo_null
			
		if logging == True and self.log == self.loginfo_null:
			self.log = self.loginfo_log
		elif logging == False and self.log == self.loginfo_log:
			self.log = self.loginfo_null
		return logging

	def loginfo_traceback (self, ctb=None):
		"""return a compact traceback tuple and log it encoded as 
		netstrings, along with this instance's __repr__, in the
		'traceback' category"""
		if ctb == None:
			ctb = prompt.compact_traceback ()
		self.loginfo_log (*traceback_encode (ctb))
		return ctb
                

def toggle (logging=None, Class=Loginfo):
	"toggle logging on/off for the Class specified or Loginfo"
	if logging == None:
		if Class.log == Class.loginfo_null:
			Class.log = Class.loginfo_log
			return True
			
		Class.log = Class.loginfo_null
		return False
		
	if logging == True and Class.log == Class.loginfo_null:
		Class.log = Class.loginfo_log
	elif logging == False and Class.log == Class.loginfo_log:
		Class.log = Class.loginfo_null
	return logging
        

# SYNOPSIS
#
# >>> from allegra import loginfo
#>>> loginfo.log ('message')
# message
# >>> loginfo.log ('message', 'info')
# info
# message
#	
# >>> try:
# ...    foobar ()
# ... except:
# ...    ctb = loginfo.traceback ()
# traceback
#   exceptions.NameError
#   name 'foobar' is not defined
#     <stdin> | ? | 2
#
# >>> logged = loginfo.Loginfo ()
# >>> logged.log ('message')
# Loginfo id="8da4e0"
# message
#	
# >>> logged.log ('message', 'info')
# info
#   Loginfo id="8da4e0"
#   message
#
# The Loginfo interface and implementation provide a simpler, yet more
# powerfull and practical logging facility than the one currently integrated
# with Python.
#
# First is uses netstrings instead of CR or CRLF delimeted lines for I/O
# encoding, solving ahead many problems of the log consumers. Second it
# is well adapted to a practical development cycle and by defaults implement
# a simple scheme that suites well a shell pipe like:
#
#	pipe < input 1> output 2> errors
#
# However "slow" this Python facily is, it offers a next-best trade-off
# between performance in production and flexibility for both debugging and
# maintenance. All debug and information logging can be effectively disabled,
# either skipped in case of:
#
#	assert None == loginfo.log (...)
#
# or simply dropped, yielding not access to possibly blocking or buffering
# process handling the log output. The ability to filter out or filter in
# log at the instance or class level is enough to satisfy the most demanding
# application administrator (as for categories, there are none defined, do
# as it please you ;-).
#
# Last but not least, the loginfo_log is compatible with asyncore logging 
# interfaces (which is no wonder, it is inspired from Medusa's original
# logging facility module).
#
#
# CAVEAT!
#
# since Loginfo instances update their own namespace with bound methods,
# they actually cycle, referencing themselves. so, when toggling off is
# a requirement if you need to finalize an instance that has been 
# explicitely logged in or out.
#
# the trade-off is the following: most toggling happens at the class level
# in practice. From development to production, instance loginfo toggling
# will disapear. And if you ask to log an object at runtime, it's a practical
# way to *not* finalize it: you're observing something! And that's even more
# true if you have to manipulate instances in production ...
#
# Simple but not obvious :-)
#
#
# One Logger Only
#
# As time and applications go by, it made sense to do with only one logger
# facility, a root logger. That's the model of log4j, but with an extra
# simplification: STDOUT and STDERR are replaced by loginfo's interfaces
# and implementation.
#
# If you 
#
# >>> print "something"
#
# in your application, it will actually be logged without categories nor
# context, directly to STDOUT. In the debug outline mode, this is exactly
# similar to writing "something" out with a newline at the end. However,
# in optimized mode, those print statement will be encoded in netstrings
# and without newline.
#
# Also, when an uncatched exception is raised, it will be logged as an
# outline or a netstring (or a multiline classic traceback, for people
# who really need that at debug time).
#
# The rational is that if your application needs to write to a file in all
# case, it either does not need a log or that file should not be STDOUT.
# Similarly, if your application does demand an error log, there is no
# reason not to have them writen to STDERR, preferrably in a format that is
# simple and safe to parse and present.
#
# 
# Practicality beats purity
#
# Satisfying a demand of Andrew Dalke, loginfo gives the option of classic
# and compact tracebacks. The later are encoded in netstring and outlined
# at debug time, the former are allways multiline strings (the original
# format) that can be parsed by existing Python development tools.
#
# If you do use those tools to lookup source code at development time, do
#
# if __debug__:
#        Loginfo.loginfo_traceback = Loginfo.loginfo_classic_traceback
#        loginfo.traceback = loginfo._classic_traceback
#
# 