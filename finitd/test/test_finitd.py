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
import copy
import time
import shutil
import datetime

import finitd.conf
from finitd.test import *

base_dir = os.path.join(os.getcwd(), 'test.%s' % datetime.datetime.now().isoformat())
os.mkdir(base_dir)

def content(filename):
    return open(filename).read()

def filename(config, filename):
    return os.path.join(config.child.chdir(), filename)

def stdout(config):
    return filename(config, config.child.stdout())

def stderr(config):
    return filename(config, config.child.stderr())

def pidfile(config):
    return filename(config, config.options.pidfile())

def callerName():
    return sys._getframe(2).f_code.co_name

def resetConfig(config):
    # Breaks on 2.4, for some reason.
    #return copy.deepcopy(config)
    for (_, g) in config:
        if hasattr(g, 'reset'):
            g.reset()
    return config
    
def getBasicConfig(caller=None):
    if caller is None:
        caller = callerName()
    #config = copy.deepcopy(finitd.conf.config)
    config = resetConfig(finitd.conf.config)
    directory = os.path.join(base_dir, caller)
    os.mkdir(directory)
    config.child.chdir.set(directory)
    config.child.stdout.set('stdout')
    config.child.stderr.set('stderr')
    config.options.pidfile.set('pid')
    # We have to explicitly set this here because the ordinary default doesn't work
    # because it doesn't reference the proper options.pidfile (it references the
    # original, not our copy)
    config.watcher.pidfile.set('pid.watcher')
    return config

def runConfig(config, finitd_command='start', caller=None):
    if caller is None:
        caller = callerName()
    fn = filename(config, caller + '.conf')
    fp = open(fn, 'w')
    config.writefp(fp, annotate=False)
    fp.close()
    ret = os.system('finitd %s %s' % (fn, finitd_command))
    # Especially on multiprocessor machines, we need to allow finitd to run
    # before we check whether it ran properly.  So we sleep for a short time here.
    # 0.01s worked on a 3Ghz Core 2 Duo, but didn't work on a 1.8Ghz Opteron.
    time.sleep(0.1)
    return ret

def runCommand(command, finitd_command='start'):
    config = getBasicConfig(caller=callerName())
    config.child.command.set(command)
    runConfig(config, finitd_command, caller=callerName())
    return config
    
def assert_file_equals(config, fn, expected):
    fn = filename(config, fn)
    assert os.path.exists(fn), \
           '%s does not exist (expected content %r)' % (fn, expected)
    s = content(fn)
    assert_equals(s, expected)

def assert_stdout_equals(config, expected):
    assert_file_equals(config, config.child.stdout(), expected)

def assert_stderr_equals(config, expected):
    assert_file_equals(config, config.child.stderr(), expected)

def test_basic():
    config = runCommand('echo foo')
    assert_stdout_equals(config, 'foo\n')
    assert_stderr_equals(config, '')

def test_redirection():
    config = runCommand('echo foo > bar')
    assert_file_equals(config, 'bar', 'foo\n')
    assert_stdout_equals(config, '')
    assert_stderr_equals(config, '')

def test_stdout_stderr_same_file():
    config = getBasicConfig()
    config.child.stderr.set(config.child.stdout())
    os.system('touch ' + filename(config, 'x'))
    # So x exists and y doesn't.  We'll ls both, which will write to both stdout
    # and stderr, and verify that the stdout file contains both lines.
    config.child.command.set('ls x y')
    runConfig(config)
    lines = sorted(open(stdout(config)))
    assert len(lines) == 2, 'Wrong number of lines: %r' % lines
    # These might need to be altered to be more cross-platform.  BSD and Linux work.
    assert 'no such file' in lines[0].lower(), \
           'Expected error message for y, got %r' % lines[0]
    assert_equals(lines[1].strip(), 'x')

def assert_pidfile(pidfilename, running=True):
    assert os.path.exists(pidfilename), \
           'pidfile %r does not exist' % pidfilename
    pid = int(content(pidfilename))
    assert os.path.exists('/proc/%s' % pid), \
           '/proc/%s (from %r) does not exist' % (pid, pidfilename)
    return pid

def test_pidfile_write():
    config = runCommand('sleep 2')
    time.sleep(1) # Give the watcher time to write the pidfile.
    pidfilename = pidfile(config)
    assert_pidfile(pidfilename)
    watcherpidfilename = filename(config, config.watcher.pidfile())
    assert_pidfile(watcherpidfilename)
    time.sleep(1.1) # Give the watcher time to exit and remove the pidfile.
    assert not os.path.exists(pidfilename), 'pidfile was not removed'
    assert not os.path.exists(watcherpidfilename), 'watcherpidfile was not removed'

def test_clearenv():
    config = getBasicConfig()
    config.options.clearenv.set(True)
    config.child.command.set('env')
    runConfig(config)
    for line in open(stdout(config)):
        assert line.startswith('FINITD_') \
            or line.startswith('PWD=') \
            or line.startswith('SHLVL='), \
               'Unexpected env variable remaining: %r' % line

def test_env_vars():
    config = getBasicConfig()
    config.options.clearenv.set(True) # Makes things easier.
    config.child.command.set('env')
    config.env.PYTHONPATH.set('.')
    runConfig(config)
    assert 'PYTHONPATH=.\n' in content(stdout(config)), \
           'Did not find expected configuration variable in env output.'

def test_basic_stop():
    config = getBasicConfig()
    config.child.command.set('sleep 10')
    runConfig(config)
    time.sleep(1) # Time to start
    pid = assert_pidfile(pidfile(config))
    print pid
    runConfig(config, finitd_command='stop')
    time.sleep(2) # Time to stop
    assert not os.path.exists(pidfile(config)), 'pidfile %r exists' % pidfile(config)
    assert not os.path.exists('/proc/%s' % pid), '/proc/%s still exists' % pid

def test_basic_restart():
    config = getBasicConfig()
    config.child.command.set('sleep 10')
    runConfig(config)
    time.sleep(1) # Time to start
    pid1 = assert_pidfile(pidfile(config))
    runConfig(config, finitd_command='restart')
    time.sleep(3) # Give the restart time to happen
    pid2 = assert_pidfile(pidfile(config))
    assert_not_equals(pid1, pid2)
    
    
if os.getuid() == 0:
    def test_setuid_setgid():
        config = getBasicConfig()
        config.child.setuid.setFromString('daemon')
        config.child.setgid.setFromString('bin')
        config.child.command.set('id')
        runConfig(config)


# Pretty sure there's no design change we can do to make this work.
#def test_basic_with_conjunction():
#    config = runCommand('echo foo && echo bar')
#    assert_stdout_equals(config, 'foo\nbar\n')
#    assert_stderr_equals(config, '')
