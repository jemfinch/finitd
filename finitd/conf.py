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
import grp
import pwd
import signal
devnull = getattr(os, 'devnull', '/dev/null')

import hieropt

class Uid(hieropt.Value):
    def type(self):
        return 'user'
    def toString(self, v):
        return pwd.getpwuid(v).pw_name
    def fromString(self, s):
        return pwd.getpwnam(s).pw_uid

class Gid(hieropt.Value):
    def type(self):
        return 'group'
    def toString(self, v):
        return grp.getgrgid(v).gr_name
    def fromString(self, s):
        return grp.getgrnam(s).gr_gid

class Signal(hieropt.Value):
    def toString(self, v):
        for name in dir(signal):
            if name.startswith('SIG') and not name.startswith('SIG_'):
                if getattr(signal, name) == v:
                    return name
        raise ValueError('Invalid signal value: %r' % v)

    def fromString(self, s):
        assert s.startswith('SIG') and not s.startswith('SIG_'), repr(s)
        return getattr(signal, s)
                    
    
class CommandGroup(hieropt.Group):
    def __init__(self, name):
        hieropt.Group.__init__(self, name)
        self.register(hieropt.Value('command',
                                    comment="""The actual command to run for the
                                               %s command.""" % self._name))
        self.register(hieropt.Value('help', default='(No help text provided)',
                                    comment="""A description of what the %s command
                                               does""" % self._name))
        
config = hieropt.Group('finitd')
child = config.register(hieropt.Group('child'))

child.register(hieropt.Value('command',
    comment="""Command to actually run. Will be parsed by /bin/sh -c."""))
child.register(hieropt.Value('stdin', default=devnull,
    comment="""File to read child program's stdin from."""))
child.register(hieropt.Value('stdout', default=devnull,
    comment="""File to write child program's stdout to."""))
child.register(hieropt.Value('stderr', default=child.stdout,
    comment="""File to write child program's stderr to."""))
child.register(hieropt.Value('chdir', default='/',
    comment="""Directory to change to before executing child."""))
child.register(hieropt.Bool('chroot', default=False,
    comment="""Whether or not to chroot in the 'chdir' directory."""))
child.register(hieropt.Int('umask', default=0,
    comment="""Umask to set before executing child."""))
child.register(Uid('setuid',
    comment="""Username to setuid to."""))
child.register(Gid('setgid',
    comment="""Group name to setgid to."""))

commands = config.register(hieropt.Group('commands'))
commands.register(hieropt.Group('stop'))
commands.stop.register(hieropt.Value('command',
    comment="""Contains an optional command to run instead of just sending a signal to
    the child pid."""))
commands.stop.register(Signal('signal', default=signal.SIGTERM,
    comment="""Determines what signal is sent to kill the process."""))
commands.register(hieropt.Group('arbitrary', Child=CommandGroup,
    comment="""finitd.commands.arbitrary contains the configuration for individual
    commands configured by the user.  Each command supports a 'command' variable which
    specifies the actual command to run."""))
env = config.register(hieropt.Group('env', Child=hieropt.Value,
    comment="""finitd.env is a group which contains variables that are placed into the
    environment before any command is run.  To set the variable FOO to 'bar' add a line
    'finitd.env.FOO: bar'."""))


options = config.register(hieropt.Group('options'))
options.register(hieropt.Value('pidfile',
    comment="""The file to write with the pid of the spawned child process."""))
options.register(hieropt.Bool('clearenv', default=False,
    comment="""Determines whether to clear the environment before executing the child
    process."""))
options.register(hieropt.Value('envdir',
    comment="""A directory wherein each file names an envrionment variable, the contents
    of that file being that variable's value."""))
options.register(hieropt.Int('restartWaitTime', default=10,
    comment="""Number of seconds to wait during a restart before attempting to start the
    process again."""))
options.register(hieropt.Int('killWaitTime', default=60,
    comment="""Number of seconds to wait during a kill before killing the process
    forcefully."""))

watcher = config.register(hieropt.Group('watcher'))
watcher.register(hieropt.Bool('wait', default=True,
    comment="""Determines whether the watcher will wait for the child and remove the
    configured pidfile.  Must be True for babysitting support."""))
# The default here breaks during tests, because it defaults to the options.pidfile
# above, rather than the one in the particular tree in which it's called.
watcher.register(hieropt.Value('pidfile',
                              default=lambda: options.pidfile() and \
                                              options.pidfile() + '.watcher',
    comment="""A file to write the pid of the watcher."""))
watcher.register(hieropt.Bool('restart', default=False,
    comment="""Determines whether the watcher will restart the child if the child
    crashes."""))
watcher.restart.register(hieropt.Int('wait', default=60,
    comment="""Determines the minimum number of seconds to wait after the most recent
    restart before restarting the child process again."""))
