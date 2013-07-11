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

"http://laurentszyster.be/blog/async_client/"

import time, socket, collections

try:
        SOCKET_FAMILIES = (socket.AF_INET, socket.AF_UNIX)
except:
        SOCKET_FAMILIES = (socket.AF_INET, )

from allegra import loginfo, async_loop, async_limits
        
        
def connect (dispatcher, addr, timeout=3.0, family=socket.AF_INET):
        "create a socket, try to connect it and schedule a timeout"
        assert (
                not dispatcher.connected and timeout > 0 and
                family in SOCKET_FAMILIES
                )
        dispatcher.client_when = time.time ()
        dispatcher.client_timeout = timeout
        try:
                dispatcher.create_socket (family, socket.SOCK_STREAM)
                dispatcher.connect (addr)
        except:
                dispatcher.loginfo_traceback ()
                dispatcher.handle_error ()
                return False
                
        assert None == dispatcher.log ('connect', 'debug')
        def connect_timeout (when):
                "if not connected and not closing yet, handle close"
                if not dispatcher.connected and not dispatcher.closing:
                        assert None == dispatcher.log (
                                'connect-timeout %f seconds' % (
                                        when - dispatcher.client_when
                                        ), 'debug'
                                )
                        dispatcher.handle_close ()

        async_loop.schedule (
                dispatcher.client_when + timeout, connect_timeout
                )
        return True


def reconnect (dispatcher):
        if dispatcher.addr:
                dispatcher.closing = False
                return connect (
                        dispatcher, 
                        dispatcher.addr, 
                        dispatcher.client_timeout, 
                        dispatcher.family_and_type[0]
                        )
                        
        return False
                

class Connections (loginfo.Loginfo):
        
        "a connection manager for async_client.Dispatcher instances"

        ac_in_meter = ac_out_meter = 0
        client_errors = client_when = client_dispatched = 0
        
        def __init__ (
                self, timeout=3.0, precision=1.0, family=socket.AF_INET
                ):
                "initialize a new client manager"
                assert (
                        timeout > 0 and precision > 0 and
                        family in SOCKET_FAMILIES
                        )
                self.client_managed = {}
                self.client_timeout = timeout
                self.client_precision = precision
                self.client_family = family
                resolved (self)
                inactive (self, timeout)
                
        def __call__ (self, dispatcher, name):
                "registed, decorate and connect a new dispatcher"
                if self.client_connect (dispatcher, name):
                        now = time.time ()
                        dispatcher.async_client = self
                        self.client_decorate (dispatcher, now)
                        key = id (dispatcher)
                        self.client_managed[key] = dispatcher
                        dispatcher.client_key = key
                        if len (self.client_managed) == 1:
                                self.client_start (now)
                else:
                        self.client_errors += 1
                return dispatcher
                
        def client_connect (self, dispatcher, name):
                "resolve and/or connect a dispatcher"
                dispatcher.client_name = name
                addr = self.client_resolved (name)
                if addr != None:
                        return connect (
                                dispatcher, addr, 
                                self.client_timeout, self.client_family
                                )

                if self.client_resolve == None:
                        self.client_unresolved (dispatcher, addr)
                        return False
                
                def resolve (addr):
                        if addr == None:
                                self.client_unresolved (dispatcher, name)
                                return
                        
                        if not connect (
                                dispatcher, addr, 
                                self.client_timeout, self.client_family
                                ):
                                self.client_errors += 1
                                
                self.client_resolve (name, resolve)
                return True
        
        def client_reconnect (self, dispatcher):
                dispatcher.closing = False
                self (dispatcher, dispatcher.client_name)
                return dispatcher.closing
        
        def client_unresolved (self, dispatcher, name):
                "assert debug log and close an unresolved dispatcher"
                assert None == dispatcher.log (
                        '%r unresolved' % (name, ), 'debug'
                        )
                self.client_errors += 1
                dispatcher.handle_close ()

        def client_start (self, when):
                "handle the client management startup"
                self.client_when = when
                async_loop.schedule (
                        when + self.client_precision, self.client_manage
                        )
                assert None == self.log ('start', 'debug')

        def client_manage (self, when):
                "test limits overflow, recure or stop"
                for dispatcher in self.client_dispatchers ():
                        if self.client_limit (dispatcher, when):
                                self.client_overflow (dispatcher)
                if self.client_managed:
                        return (
                                when + self.client_precision,
                                self.client_manage
                                ) # continue to defer
                
                self.client_stop (when)
                return None
        
        def client_dispatchers (self):
                "return a list of managed dispatchers"
                return self.client_managed.values ()
                        
        def client_overflow (self, dispatcher):
                "assert debug log and close an overflowed dispatcher"
                assert None == dispatcher.log ('limit overflow', 'debug')
                dispatcher.handle_close ()
                
        def client_meter (self, dispatcher):
                "assert debug log and account I/O meters of a dispatcher"
                assert None == dispatcher.log (
                        'in="%d" out="%d"' % (
                                dispatcher.ac_in_meter, 
                                dispatcher.ac_out_meter
                                ),  'debug'
                        )
                self.ac_in_meter += dispatcher.ac_in_meter
                self.ac_out_meter += dispatcher.ac_out_meter
                self.client_dispatched += 1

        def client_close (self, dispatcher):
                "remove the dispatcher from cache and meter dispatched"
                del self.client_managed[dispatcher.client_key]
                self.client_meter (dispatcher)
                dispatcher.async_client = None

        def client_stop (self, when):
                "handle the client management stop"
                assert None == self.log (
                        'stop errors="%d" dispatched="%d"'
                        ' seconds="%f" in="%d" out="%d"' % (
                                self.client_errors,
                                self.client_dispatched,
                                (when - self.client_when),
                                self.ac_in_meter,
                                self.ac_out_meter
                                ), 'debug')
                self.client_errors = self.client_dispatched = \
                        self.ac_in_meter = self.ac_out_meter = 0

        def close_when_done (self):
                "close all client dispatchers when done"
                for dispatcher in self.client_dispatchers ():
                        dispatcher.close_when_done ()
                        

class Cache (Connections):

        "a cache of managed connections"

        def __init__ (
                self, timeout=3.0, precision=1.0, family=socket.AF_INET
                ):
                "initialize a new client cache"
                assert (
                        timeout > 0 and precision > 0 and
                        family in SOCKET_FAMILIES
                        )
                self.client_managed = {}
                self.client_timeout = timeout
                self.client_precision = precision
                self.client_family = family
                resolved (self)
                inactive (self, timeout)
                
        def __call__ (self, Dispatcher, name):
                """return a cached or a new dispatcher, maybe resolving and
                connecting it first, closing it on connection error or if
                it's socket address cannot be resolved"""
                try:
                        return self.client_managed[name]
                        
                except KeyError:
                        pass
                dispatcher = Dispatcher ()
                if self.client_connect (dispatcher, name):
                        now = time.time ()
                        dispatcher.async_client = self
                        self.client_decorate (dispatcher, now)
                        self.client_managed[name] = dispatcher
                        dispatcher.client_key = name
                        if len (self.client_managed) == 1:
                                self.client_start (now)
                else:
                        self.client_errors += 1
                return dispatcher


class Pool (Connections):
        
        "a pool of managed connections"
        
        def __init__ (
                self, Dispatcher, name, 
                size=2, timeout=3.0, precision=1.0, family=socket.AF_INET
                ):
                "initialize a new client pool"
                assert (
                        type (size) == int and size > 1 and
                        timeout > 0 and precision > 0 and
                        family in SOCKET_FAMILIES
                        )
                self.client_managed = []
                self.client_pool = size
                self.client_name = name
                self.client_called = 0
                self.Client_dispatcher = Dispatcher
                self.client_timeout = timeout
                self.client_precision = precision
                self.client_family = family
                resolved (self)
                inactive (self, timeout)
                
        def __call__ (self):
                """return the next dispatcher pooled or instanciate a new
                one, maybe resolving and connecting it first, closing it on 
                connection error or if it's socket address cannot be 
                resolved"""
                size = len (self.client_managed)
                if size >= self.client_pool:
                        self.client_called += 1
                        return self.client_managed[self.client_called % size]
                
                now = time.time ()
                dispatcher = self.Client_dispatcher ()
                if self.client_connect (dispatcher, self.client_name):
                        dispatcher.async_client = self
                        self.client_decorate (dispatcher, now)
                        self.client_managed.append (dispatcher)
                        if len (self.client_managed) == 1:
                                self.client_start (now)
                else:
                        self.client_errors += 1
                return dispatcher
        
        def client_reconnect (self, dispatcher):
                return False # useless for a cached dispatcher!

        def client_dispatchers (self):
                "return a list of dispatchers pooled"
                return list (self.client_managed)
                        
        def client_close (self, dispatcher):
                "remove the dispatcher from pool and increment dispatched"
                self.client_meter (dispatcher)
                self.client_managed.remove (dispatcher)
                dispatcher.async_client = None


def resolved (connections):
        "allways resolved for unresolved dispatcher address"
        connections.client_resolved = (lambda addr: addr)
        connections.client_resolve = None
        return connections


def meter (dispatcher, when):
        "decorate a client dispatcher with stream meters"
        async_limits.meter_recv (dispatcher, when)
        async_limits.meter_send (dispatcher, when)
        def close ():
                del (
                        dispatcher.recv, 
                        dispatcher.send, 
                        dispatcher.close
                        )
                dispatcher.close ()
                dispatcher.async_client.client_close (dispatcher)
                
        dispatcher.close = close
        
def no_limit (dispatcher, when):
        return False
        
        
def unlimited (connections):
        "meter I/O for unlimited client streams"
        connections.client_decorate = meter
        connections.client_limit = no_limit
        return connections
        

def inactive (connections, timeout):
        "meter I/O and limit inactivity for client streams"
        assert timeout > 0
        def decorate (dispatcher, when):
                meter (dispatcher, when)
                dispatcher.limit_inactive = connections.client_inactive
                
        connections.client_decorate = decorate
        connections.client_inactive = timeout
        connections.client_limit = async_limits.inactive
        return connections


def limited (connections, timeout, inBps, outBps):
        "throttle I/O and limit inactivity for managed client streams"
        assert (
                timeout > 0 and
                type (inBps ()) == int and inBps () > 0 and
                type (outBps ()) == int and outBps () > 0
                )
        def throttle (dispatcher, when):
                "decorate a client dispatcher with stream limits"
                async_limits.meter_recv (dispatcher, when)
                async_limits.meter_send (dispatcher, when)
                dispatcher.limit_inactive = timeout
                async_limits.throttle_readable (
                        dispatcher, when, connections.ac_in_throttle_Bps
                        )
                async_limits.throttle_writable (
                        dispatcher, when, connections.ac_out_throttle_Bps
                        )
                def close ():
                        del (
                                dispatcher.recv, 
                                dispatcher.send, 
                                dispatcher.readable,
                                dispatcher.writable,
                                dispatcher.close
                                )
                        dispatcher.close ()
                        dispatcher.async_client.client_close (dispatcher)
                        
                dispatcher.close = close

        connections.client_decorate = throttle
        connections.ac_in_throttle_Bps = inBps
        connections.ac_out_throttle_Bps = outBps
        connections.client_limit = async_limits.limit
        return connections


def rationed (connections, timeout, inBps, outBps):
        "ration I/O and limit inactivity for managed client streams"
        assert (
                timeout > 0 and
                type (inBps) == int and inBps > 0 and
                type (outBps) == int and outBps > 0
                )
        connections.ac_in_ration_Bps = inBps
        connections.ac_out_ration_Bps = outBps
        def throttle_in ():
                return int (connections.ac_in_ration_Bps / max (len (
                        connections.client_managed
                        ), 1))

        def throttle_out ():
                return int (connections.ac_out_ration_Bps / max (len (
                        connections.client_managed
                        ), 1))

        return limited (connections, timeout, throttle_in, throttle_out)
        


class Pipeline (object):
        
        "a pipeline mix-in for dispatcher"

        #pipeline_sleeping = False
        pipeline_pipelining = False
        pipeline_keep_alive = False

        def pipeline_set (self, requests=None, responses=None):
                "set new requests and responses deque"
                self.pipeline_requests = requests or collections.deque ()
                self.pipeline_responses = responses or collections.deque ()

        #def pipeline (self, request):
        #        "pipeline a new request, wake up if sleeping"
        #        self.pipeline_requests.append (request)
        #        if self.pipeline_sleeping:
        #                self.pipeline_sleeping = False
        #                self.pipeline_wake_up ()

        def pipeline_wake_up (self):
                requests = self.pipeline_requests
                if self.pipeline_pipelining and len (requests) > 1:
                        self.pipeline_requests = deque ()
                        self.output_fifo.extend ((
                                request[0] for request in requests
                                ))
                        self.pipeline_responses.extend (requests)
                else:
                        request = self.pipeline_requests.popleft ()
                        self.output_fifo.append (request[0])
                        self.pipeline_responses.append (request)
                
                        