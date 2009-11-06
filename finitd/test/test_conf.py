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

import grp

from finitd import Config, conf
from finitd.test import *
from hieropt.test.test_hieropt import assert_write_then_read_equivalence

def test_Uid():
    uid = conf.Uid('uid')
    uid.setFromString('root')
    assert_equals(uid(), 0)
    assert_equals(str(uid), 'root')

def test_Gid():
    gid = conf.Gid('gid')
    # Can't test for 'root' here because BSD doesn't have a root group.
    gid.setFromString('daemon')
    assert_equals(gid(), grp.getgrnam('daemon').gr_gid)
    assert_equals(str(gid), 'daemon')

def test_Signal():
    sig = conf.Signal('sig')
    sig.setFromString('SIGKILL')
    assert_equals(sig(), 9)
    assert_equals(str(sig), 'SIGKILL')
    sig.setFromString('SIGTERM')
    assert_equals(sig(), 15)
    assert_equals(str(sig), 'SIGTERM')

def test_conf_config():
    assert_write_then_read_equivalence(conf.config)

def test_watcher_pidfile():
    assert_equals(conf.config.options.pidfile(), None)
    assert_equals(conf.config.watcher.pidfile(), None)
    conf.config.options.pidfile.set('pid')
    assert_equals(conf.config.watcher.pidfile(), 'pid.watcher')
