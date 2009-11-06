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
import sys
import errno
import syslog

def error(msg, code=-1):
    sys.stderr.write(msg.strip())
    sys.stderr.write('\n')
    sys.exit(code)

class SyslogFile(object):
    def __init__(self, level=syslog.LOG_INFO):
        self.level = level
        
    def write(self, s):
        s = s.strip()
        if s:
            syslog.syslog(self.level, s)

    def writelines(self, L):
        for s in L:
            self.write(s)

for s in dir(syslog):
    if s.startswith('LOG_'):
        setattr(SyslogFile, s, getattr(syslog, s))

def getPidFromFile(pidfile):
    if not os.path.exists(pidfile):
        return None
    try:
        fp = open(pidfile)
    except EnvironmentError, e:
        error('Cannot open pidfile %r: %s' % (pidfile, e))
    pid = int(fp.read())
    fp.close()
    return pid

def checkProcessAlive(pid):
    try:
        os.kill(pid, 0)
        return pid
    except OSError, e:
        if e.errno == errno.ESRCH: # No such process.
            return 0
        else:
            return pid # XXX Should do more checking, based on config.
