###
# Copyright (c) 2009, Juju, Inc.
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer. 
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of the author of this software nor the names of
#       the contributors to the software may be used to endorse or
#       promote products derived from this software without specific
#       prior written permission. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. 
###

import os
import tempfile

from finitd import util
from finitd.test import *

def test_checkProcessAlive():
    assert util.checkProcessAlive(os.getpid()), 'Current process is definitely alive.'
    pid = os.fork()
    if not pid:
        os._exit(0) # Just exit if the child, so we have a dead process.
    os.waitpid(pid, 0) # Wait for the child to exit.
    assert not util.checkProcessAlive(pid)

def test_getPidFromFile():
    fp = tempfile.NamedTemporaryFile(delete=False)
    fp.write('123\n')
    fp.close()
    assert_equals(util.getPidFromFile(fp.name), 123)
    os.remove(fp.name)
