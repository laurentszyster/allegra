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

from distutils.core import setup

setup (
        name='Allegra', 
        version='0.63', 
        description='Asynchronous Network Peer Programming',
        author='Laurent Szyster',
        author_email='contact@laurentszyster.be',
        url='http://laurentszyster.be/blog/allegra/',
        packages=['allegra'],
        package_dir = {'allegra': 'lib'}
        )