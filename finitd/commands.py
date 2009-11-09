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

# start stop restart reload kill

import os
import sys
import time
import errno
import signal

import util
import compat
from util import error
from OrderedDict import OrderedDict

def waitFor(seconds):
    until = time.time() + seconds
    while time.time() < until:
        time.sleep(1)

class InvalidConfiguration(Exception):
    pass

class Command(object):
    def __init__(self, config, name=None):
        if name is None:
            name = self.__class__.__name__.lower()
        self.name = name
        self.config = config

    def checkConfig(self, config):
        return # No checking performed by default.

    @classmethod
    def help(cls):
        return cls.__doc__

    def run(self, args, environ):
        raise NotImplementedError

    def checkProcessAlive(self, pid=None):
        if pid is None:
            pid = self.getPidFromFile()
        if pid is None:
            return 0
        return util.checkProcessAlive(pid)

    def getPidFromFile(self, pidfile=None):
        if pidfile is None:
            pidfile = self.config.options.pidfile()
            if pidfile is None:
                error('finitd.options.pidfile is not configured.')
        return util.getPidFromFile(pidfile)

    def writePidfile(self, pid, pidfile=None):
        if pidfile is None:
            pidfile = self.config.options.pidfile()
        if pidfile is not None:
            fp = open(pidfile, 'w')
            try:
                fp.write('%s\n' % pid)
            finally:
                fp.close()

    def removePidfile(self, pidfile=None):
        if pidfile is None:
            pidfile = self.config.options.pidfile()
        if pidfile is not None:
            os.remove(pidfile)

    def chdir(self):
        try:
            os.chdir(self.config.child.chdir())
        except EnvironmentError, e:
            error('chdir to %r failed: %s' % (self.config.child.chdir(), e))

    def chroot(self):
        if self.config.child.chroot():
            os.chroot(self.config.child.chdir())

    def umask(self):
        os.umask(self.config.child.umask())

    def setuid(self):
        uid = self.config.child.setuid()
        if uid is not None:
            os.setuid(uid)

    def setgid(self):
        gid = self.config.child.setgid()
        if gid is not None:
            os.setgid(gid)

    def execute(self, environ, command=None):
        if command is None:
            command = self.config.child.command()
        os.execle('/bin/sh', 'sh', '-c', 'exec ' + command, environ)


class start(Command):
    """Starts the configured child process."""
    def checkConfig(self, config):
        if config.options.pidfile() is None:
            raise InvalidConfiguration('finitd.options.pidfile must be configured.')
        if config.watcher.restart() and not config.watcher.wait():
            raise InvalidConfiguration('finitd.watcher.wait must be set if '
                                       'finitd.watcher.restart is set.')
        if config.child.setuid() and os.getuid():
            raise InvalidConfiguration('You must be root if finitd.child.setuid is set.')
        if config.child.setgid() and os.getuid():
            raise InvalidConfiguration('You must be root if finitd.child.setgid is set.')
        
    def run(self, args, environ):
        pid = self.checkProcessAlive()
        if pid:
            # (the exit code used here matches start-stop-daemon)
            error("""Process appears to be alive at pid %s.  If this is not the process
            you're attempting to start, remove the pidfile %r and start again.""" %
                  (pid, self.config.options.pidfile()), code=1)

        # Before we fork, we replace sys.stdout/sys.stderr with sysloggers
        sys.stdout = util.SyslogFile()
        sys.stderr = util.SyslogFile(util.SyslogFile.LOG_ERR)

        pid = os.fork()
        if pid:
            os._exit(0)

        # Set a new session id.
        sid = os.setsid()
        if sid == -1:
            error('setsid failed') # So apparently errno isn't available to Python...

        self.chdir()
        self.chroot()

        # Close open files before going into watcher loop.
        try:
            # "Borrowed" from the subprocess module ;)
            MAXFD = os.sysconf('SC_OPEN_MAX')
        except:
            MAXFD = 256
        os.closerange(0, MAXFD)
        fd = os.open(self.config.child.stdin(), os.O_CREAT | os.O_RDONLY)
        assert fd == 0, 'stdin fd = %r' % fd
        fd = os.open(self.config.child.stdout(), os.O_CREAT | os.O_WRONLY)
        assert fd == 1, 'stdout fd = %r' % fd
        if self.config.child.stderr() != self.config.child.stdout():
            fd = os.open(self.config.child.stderr(), os.O_CREAT | os.O_WRONLY)
            assert fd == 2, 'stderr fd = %r' % fd
        else:
            os.dup2(1, 2)

        
        lastRestart = 0
        restartWait = self.config.watcher.restart.wait()
        watcherPid = os.getpid()
        def log(s):
            print 'Watcher[%s]: %s' % (watcherPid, s)
        while time.time() > lastRestart + restartWait:
            lastRestart = time.time()
            log('starting process')
            pid = os.fork() # This spawns what will become the actual child process.
            if pid:
                def sigusr1(signum, frame):
                    log('received SIGUSR1, removing watcher pidfile and exiting')
                    # XXX All we really need to do is configure not to restart, right?
                    # Originally I removed both pidfiles here, but it's needed in order
                    # to kill the child process, which must necessarily happen after the
                    # watcher exits, if the watcher is configured to restart the child.
                    self.removePidfile(self.config.watcher.pidfile())
                    os._exit(0)
                signal.signal(signal.SIGUSR1, sigusr1)
                log('child process started at pid %s' % pid)
                self.writePidfile(pid)
                if self.config.watcher.wait():
                    self.writePidfile(watcherPid, self.config.watcher.pidfile())
                    (_, status) = os.waitpid(pid, 0)
                    log('process exited with status %s' % status)
                    # Remove pidfile when child has exited.
                    self.removePidfile()
                    if self.config.watcher.restart() and status != 0:
                        command = self.config.watcher.restart.command()
                        if command:
                            log('running %r before restart' % command)
                            status = os.system(command)
                            if status:
                                log('%r exited with nonzero status %s, exiting' % status)
                                break
                        continue # Not strictly necessary, but we're way nested here.
                    else:
                        break
                else:
                    break
            else:
                # This is the child process, pre-exec.
                self.umask()
                self.setgid()
                self.setuid()
                # Now we're ready to actually spawn the process.
                self.execute(environ)
        self.removePidfile(self.config.watcher.pidfile())
        log('exiting')
        os._exit(0)


    

class debug(start): # subclassing start to inherit checkConfig
    """Starts the configured child process without daemonizing or redirecting
    stdin/stdout/stderr, for debugging problems with starting the process."""
    def run(self, args, environ):
        self.chdir()
        self.chroot()
        self.umask()
        self.setgid()
        self.setuid()
        self.execute(environ)
    

class stop(Command):
    """Stops the running child process by sending it SIGTERM."""
    def checkConfig(self, config):
        if not config.options.pidfile():
            raise InvalidConfiguration('Cannot stop the process without a configured'
                                       'finitd.options.pidfile.')
        if config.commands.stop.command() and config.commands.stop.signal():
            raise InvalidConfiguration('finitd.commands.stop.command and '
                                       'finitd.commands.stop.signal cannot be '
                                       'configured simultaneously.')
    def run(self, args, environ):
        self.chdir() # If the pidfile is a relative pathname, it's relative to here.
        pid = self.checkProcessAlive()
        if pid:
            if self.config.watcher.pidfile() and self.config.watcher.restart():
                watcherPid = self.getPidFromFile(self.config.watcher.pidfile())
                if watcherPid:
                    # Tell the watcher to remove the pidfile and exit.
                    os.kill(watcherPid, signal.SIGUSR1)
                    time.sleep(1) # Wait to make sure the watcher exits.
            if self.config.commands.stop.command():
                self.execute(environ, self.config.commands.stop.command())
            else:
                os.kill(pid, self.config.commands.stop.signal())
        else:
            print 'Process is not running.'
            sys.exit(1) # to match start-stop-daemon
        
class restart(Command):
    """Restarts the process.  Equivalent to `stop` followed by `start`"""
    def run(self, args, environ):
        stop(self.config).run([], environ)
        waitFor(self.config.options.restartWaitTime())
        pid = self.checkProcessAlive()
        if pid:
            error('Process is still running at pid %s' % pid)
        start(self.config).run([], environ)

class kill(Command):
    """Attempts to stop the process ordinarily, but if that fails, sends the process
    SIGKILL."""
    def run(self, args, environ):
        stop(self.config).run([], environ)
        waitingUntil = time.time() + self.config.options.killWaitTime()
        while time.time() < waitingUntil and self.checkProcessAlive():
            time.sleep(1)
        if self.checkProcessAlive():
            os.kill(self.getPidFromFile(), signal.SIGKILL)
            time.sleep(self.config.options.restartWaitTime())
            if self.checkProcessAlive():
                error('Cannot kill process %s' % self.getPidFromFile())

class status(Command):
    """Returns whether the process is alive or not.  Prints a message and exits with
    error status 0 if the process exists, with error status 1 if the process does not
    exist."""
    def run(self, args, environ):
        pid = self.checkProcessAlive()
        if pid:
            print 'Process is running at pid %s' % pid
            sys.exit(0)
        else:
            print 'Process is not running.'
            sys.exit(1)

class annotate(Command):
    """Annotates the given configuration file and outputs it to stdout.  Useful with
    /dev/null as a configuration file just to output an annotated configuration file
    ready for modification."""
    def run(self, args, environ):
        self.config.writefp(sys.stdout)

class ArbitraryCommand(Command):
    def __init__(self, config, name):
        self.command = config.commands.arbitrary.get(name)
        Command.__init__(self, config, name)

    def checkConfig(self, config):
        if not self.command.command():
            raise InvalidConfiguration('finitd.commands.%s.command must be set.'
                                       % self.name)

    def help(self):
        return self.command.help() or ''
    
    def run(self, args, environ):
        self.chdir()
        self.chroot()
        os.system(self.command.command())
        #self.execute(environ, self.command.command())

commands = [
    'start',
    'stop',
    'kill',
    'restart',
    'status',
    'debug',
    'annotate',
]
