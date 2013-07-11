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

"http://laurentszyster.be/blog/allegra/doc/"

__all__ = [
        #
        # Asynchronous Network Peer Programming
        #
        'netstring', 'prompt', 'loginfo', 
        'async_loop', 'finalization', 'async_core',
        'select_trigger', 'thread_loop', 'sync_stdio', 
        'async_net', 'async_chat', 'producer', 'collector', 'reactor', 
        'async_limits', 'async_server', 'async_client', 
        'synchronized', 'timeouts',
        #
        # Major Internet Application Protocols
        #
        'ip_peer', 'dns_client', 
        'tcp_server', 'tcp_client', 
        'mime_headers', 'mime_reactor',
        # 'smtp_client', 'pop_client', 'nnrp_client', 
        'http_reactor', 'http_client', 'http_server', 
        'xml_dom', 'xml_unicode', 'xml_utf8', 'xml_reactor',
        #
        # PNS, The Reference Implementation
        #
        'sat', 'pns_model', 
        'pns_sat', 'pns_mime', 'pns_xml', 'pns_rss', # 'pns_html', 
        'pns_tcp', 'pns_resolution', 'pns_inference', 'pns_udp', 
        'pns_peer', 'pns_client', 'pns_articulator', 
        #
        # Allegra PRESTo!
        #
        'presto', 'presto_http', 
        'presto_prompt', 'presto_pns', # 'presto_bsddb', 
        #
        # The Last DNS Application
        #
        # 'pns_dns'
        ]

__author__ = 'Laurent A.V. Szyster <contact@laurentszyster.be>'