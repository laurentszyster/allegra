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

"http://laurentszyster.be/blog/thread_loop/"

import threading, collections

from allegra import netstring, loginfo, finalization, select_trigger


class Trunked_deque (object):
        
        "a deque implementation to trunk protected deque safely"

        def __len__ (self):
                "return 1, a trunked deque has allways one item" 
                return 1
                
        def __getitem__ (self, index):
                "return None or raise IndexError"
                if index == 0:
                        return None
                        
                raise IndexError, 'trunked deque'
                
        def append (self, item): 
                "drop any item appended to the deque"
                pass

        def popleft (self): 
                "return None, the closing item for a deque consumer"
                return None
        
        pop = popleft
        
        appendleft = append


class Protected_deque (object):

        "a thread-safe wrapper for a deque"

	def __init__ (self, queue=None):
		self.deque = collections.deque (queue or [])
		self.mon = threading.RLock ()
		self.cv = threading.Condition (self.mon)

        def __repr__ (self):
                "return a safe netstring representation of the deque"
                r = []
                try:
                        self.cv.acquire ()
                        l = len (self.deque)
                        for item in self.deque:
                                try:
                                        r.append ('%r' % (item,))
                                except:
                                        r.append (
                                                'item id="%x"' % id (item)
                                                )
                finally:
                        self.cv.release ()
                return netstring.encode ((
                        'protected_deque queued="%d"' % l,
                        netstring.encode (r)
                        ))
        
	def __len__ (self):
                "return the queue's length"
		try:
			self.cv.acquire ()
			l = len (self.deque)
		finally:
			self.cv.release ()
		return l

        def __getitem__ (self, index):
                "return the queue's length"
                try:
                        self.cv.acquire ()
                        return self.deque[index]
                                
                finally:
                        self.cv.release ()
                
        def append (self, item):
                "push an item at the end the deque and notify"
                try:
                        self.cv.acquire ()
                        self.deque.append (item)
                        self.cv.notify ()
                finally:
                        self.cv.release ()
        
        __call__ = append
                
        def popleft (self):
                "wait for a first item in the deque and pop it"
                try:
                        self.cv.acquire ()
                        while len (self.deque) == 0:
                                self.cv.wait ()
                        item = self.deque.popleft ()
                finally:
                        self.cv.release ()
                return item

        def appendleft (self, item):
                "push an item of items in front of the deque"
                try:
                        self.cv.acquire ()
                        self.deque.appendleft (item)
                        self.cv.notify ()
                finally:
                        self.cv.release ()

        def pop (self):
                "wait for a last item in the deque and pop it"
                try:
                        self.cv.acquire ()
                        while len (self.deque) == 0:
                                self.cv.wait ()
                        item = self.deque.pop ()
                finally:
                        self.cv.release ()
                return item

        def trunk (self):
                """Replace the deque with a trunked deque implementation
                and return the replaced deque instance."""
                try:
                        self.cv.acquire ()
                        trunked = self.deque
                        self.deque = Trunked_deque ()
                finally:
                        self.cv.release ()
                return trunked
                #
                # In effect, trunking implies closing a running thread loop 
                # and dropping any item queued thereafter, which is precisely 
                # The Right Thing To Do when a thread loop queue is stopped: 
                # prevent accessors to push  references that won't be popped 
                # out and leak.                
                

class Thread_loop (threading.Thread, select_trigger.Select_trigger):

        "a thread loop, with thread-safe asynchronous logging"

	def __init__ (self, queue=None):
		self.thread_loop_queue = queue or Protected_deque ()
		select_trigger.Select_trigger.__init__ (self)
		threading.Thread.__init__ (self)
		self.setDaemon (1)

	def __repr__ (self):
		return 'thread-loop id="%x"' % id (self)

	def run (self):
                """The Thread Loop
                
                If thread_loop_init() is True call queued instance until
                None is popped or and exception is raised and not catched
                by thread_loop_throw. Finally, if thread_loop_delete() is
                True, trunk the thread loop queue.
                """
		if self.thread_loop_init ():
                        next = self.thread_loop_queue.popleft # ? maybe safer
			while True:
				queued = next () # ... sure faster
				if queued == None:
					break

				try:
				        queued[0] (*queued[1])
				except:
					if self.thread_loop_throw ():
                                                del queued
                                                break
                                        
                                else:
                                        del queued
                        #
                        # note that I make sure to delete the tuple which
                        # would otherwise hold a reference to the method and
                        # arguments of the call threaded, preventing garbage
                        # collection hence finalization and was the source
                        # of subtle bugs ...
                        #
		if self.thread_loop_delete ():
                        trunked = self.thread_loop_queue.trunk ()
                        if trunked:
                                assert None == self.select_trigger_log (
                                        netstring.encode ([
                                                '%r' % (i,) for i in trunked
                                                ]), 'debug'
                                        )
		#
		# ... continue with the Select_trigger.finalization, unless
                # there are circular references for this instance, caveat!

        def thread_loop (self, queued):
                "assert debug log and push a simple callable in the queue"
                assert None == self.log ('%r %r' % queued, 'queued')
                self.thread_loop_queue (queued)

        def thread_loop_stop (self):
                "assert debug log and push the stop item None in the queue"
                assert None == self.log ('stop-when-done', 'debug')
                self.thread_loop_queue (None)

	def thread_loop_init (self):
                "return True, assert a debug log of the thread loop start"
		assert None == self.log ('start', 'debug')
		return True
                
        def thread_loop_throw (self):
                "return False, log a compact traceback via the select trigger"
                self.select_trigger_traceback ()
                return False

        def thread_loop_delete (self):
                "return True, assert a debug log of the thread loop start"
                assert None == self.log ('stop', 'debug')
                return True


class Synchronizer (loginfo.Loginfo):

        def __init__ (self, size=2):
                self.synchronizer_size = size
                self.synchronized_thread_loops = []
                self.synchronized_instance_count = []
                self.synchronized_count = 0

        def __repr__ (self):
                return 'synchronizer pid="%x" count="%d"' % (
                        id (self), self.synchronized_count
                        )

        def synchronizer_append (self):
                assert None == self.log (
                        'append %d' % len (self.synchronized_thread_loops), 
                        'synchronizer'
                        )
                t = Thread_loop ()
                t.thread_loop_queue.synchronizer_index = len (
                        self.synchronized_thread_loops
                        )
                self.synchronized_thread_loops.append (t)
                self.synchronized_instance_count.append (0)
                t.start ()
                
        def synchronize (self, instance):
                assert not hasattr (instance, 'synchronized')
                if self.synchronized_count == len (
                        self.synchronized_thread_loops
                        ) < self.synchronizer_size:
                        self.synchronizer_append ()
                index = self.synchronized_instance_count.index (
                        min (self.synchronized_instance_count)
                        )
                t = self.synchronized_thread_loops[index]
                instance.synchronized = t.thread_loop_queue
                instance.select_trigger = t.select_trigger 
                self.synchronized_instance_count[index] += 1
                self.synchronized_count += 1
                assert None == self.log ('%r' % instance, 'synchronized')

        def desynchronize (self, instance):
                assert hasattr (instance, 'synchronized')
                i = instance.synchronized.synchronizer_index
                count = self.synchronized_instance_count[i]
                self.synchronized_count += -1
                self.synchronized_instance_count[i] += -1
                instance.select_trigger = instance.synchronized = None
                if self.synchronized_count == 0:
                        assert None == self.log ('stop %d threads' % len (
                                self.synchronized_thread_loops
                                ), 'synchronizer')
                        for t in self.synchronized_thread_loops:
                                t.thread_loop_queue (None)
                        self.synchronized_thread_loops = []
                assert None == self.log ('%r' % instance, 'desynchronized')


def synchronize (instance):
        if instance.synchronizer == None:
                instance.__class__.synchronizer = Synchronizer (
                        instance.synchronizer_size
                        )
        instance.synchronizer.synchronize (instance)


def desynchronize (instance):
        instance.synchronizer.desynchronize (instance)


def synchronized (instance):
        assert isinstance (instance, finalization.Finalization) 
        if instance.synchronizer == None:
                instance.__class__.synchronizer = Synchronizer (
                        instance.synchronizer_size
                        )
        instance.synchronizer.synchronize (instance)
        instance.finalization = instance.synchronizer.desynchronize

        
# Notes about the Synchronizer
#
# The purpose is to but deliver non-blocking interfaces to synchronous API.
#
# The synchronizer is an resizable array of thread loop queues. Synchronized
# instances are attached to one of these queues. When a synchronized instance
# is finalized, that reference is released and the array is notified. When no
# more instance is attached to a thread loop queue, its thread exits. If the
# limit set on the array size is not reached, a new thread loop is created for
# each new synchronized instance. The default limit is set to 4.
#
# This interface is purely asynchronous: methods synchronized should be able
# to access the select_trigger to manipulate the Synchronizer, or more
# mundanely to push data to asynchat ...
#
#
# Limits
#
# There is no easy way to prevent an instance to stall its thread loop queue
# and all the other instances methods synchronized to it. The only practical
# algorithm to detect a stalled method (and "fix" it), is to set a limit on
# the size of the synchronized queue and when that limit is reached to replace
# the stalled thread loop by a new one. However, this would leave the stalled
# thread to hang forever if the stalling method is running amok or blocking
# forever too. Setting a timeout on each synchronized method is impossible
# since there is no way to infer reliably a maximum execution time, certainly
# in such case of concurrent processes.
#
# Basicaly, there is no practical and effective way to fix a thread broken by
# an infinite loop or a stalled-forever wait state. So, this implementation
# does not even attempt to correct the effects of such bugs on the other
# synchronized instance methods.
#
#
# Beware!
#
# Synchronized methods must be tested separately. Yet it is trivial, because
# you may either test them asynchronously from within an async_loop host or,
# since they are synchronous, directly from the Python prompt.
#
# My advice is to use synchronized method in two cases. Either you don't want
# to learn asynchronous programming (don't have time for that). Or you know
# how, but need to access a blocking API that happens to be thread safe and
# releases the Python GIL.
#
# For instance:
#
#         os.open (...).read ()
#
# or
#
#        bsddb.db.DB ().open (...)
#
# may be blocking and should be synchronized.
        