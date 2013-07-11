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

"http://laurentszyster.be/blog/finalization/"


from allegra import loginfo, async_loop


# Finalize

class Finalization (object):

        finalization = None
        
        async_finalized = async_loop._finalized

        def __del__ (self):
                if self.finalization != None:
                         self.async_finalized.append (self)


def collect ():
        import gc
        collected = gc.collect ()
        if collected == 0:
                return
        
        assert None == loginfo.log ('%d' % collected, 'collected')
        for cycle in gc.garbage:
                try:
                        cylce.finalization = None
                except:
                        pass
                assert None == loginfo.log ('%r' % cycle, 'garbage')
        

# Branch

class Branch (Finalization):

	def __init__ (self, finalizations):
		self.finalizations = finalizations

	def __call__ (self, finalized):
		for finalization in self.finalizations:
			finalization (finalized)

def branch (branched, finalization):
	try:
		branched.finalization.finalizations.append (finalization)
	except:
		branched.finalization = Branch ([
			branched.finalization, finalization
			])
		
		
# Continue

class Continuation (object):

        finalization = None
        async_finalized = async_loop._finalized
        
        def __call__ (self): pass

        def __del__ (self):
                if self.finalization != None:
                         self.async_finalized.append (self)

	
def continuation (finalizations):
	"combines continuations into one execution path"
        i = iter (finalizations)
	first = continued = i.next ()
        try:
        	while True:
                        continued.finalization = i.next ()
                        continued = continued.finalization
        except StopIteration:
                pass
	return first, continued


class Continue (Continuation):
        
	def __init__ (self, finalizations):
		self.__call__, self.continued = continuation (
                        finalizations
                        )

# Join
#
# the equivalent of "thread joining" with finalization does not really need 
# a specific interface because it is enough to set the "joining" finalized
# as the finalization of all "joined" finalized.
#
#        joined.finalization = joining
#
# how simple ...

def join (finalizations, continuation):
        def finalize (finalized):
                for joined in finalizations:
                        joined.finalization = continuation
        return finalize
                

class Join (Continuation):

        def __init__ (self, finalizations):
                self.finalizations = finalizations
        
        def __call__ (self, finalized):
                if self.finalizations:
                        # start
                        for joined in self.finalizations:
                                joined.finalization = self
                        self.finalizations = None
                #
                # join
                