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
import syslog
import optparse
import textwrap

from finitd.conf import config
from finitd import util, commands

def makeEnvironment(config):
    # Do we start with a clear environment or our existing one?
    if config.options.clearenv():
        environ = {}
    else:
        environ = os.environ.copy()

    # Add configuration variables to environment variables.
    for (name, value) in config:
        if value.expectsValue() and value.isSet():
            name = name.upper().replace('.', '_')
            environ[name] = str(value)
            if value._name == 'pidfile':
                pid = util.getPidFromFile(value())
                if pid and util.checkProcessAlive(pid):
                    environ[name[:-4]] = str(pid)

    # Set configured environment variables.
    envdir = config.options.envdir()
    if envdir:
        for name in os.listdir(envdir):
            value = file(os.path.join(envdir, name)).read()
            environ[name] = value
    for child in config.env.children():
        environ[child._name] = str(child)

    return environ

def makeHelp(commands,
             configFilename=None,
             usage='%prog <configfile> [options] <command>'):
    if commands:
        usage = usage.replace('<command>', '{%s}' %
                              '|'.join(command.name for command in commands))
    indent = '\t' * 3
    progname = os.path.basename(sys.argv[0])
    parts = ['Commands:']
    for command in commands:
        if configFilename is not None:
            name = '%s %s %s' % (progname, configFilename, command.name)
        else:
            name = command.name
        parts.extend([
            name,
            textwrap.fill(command.help(),
                          width = 70 - len(indent.replace('\t', ' '*8)),
                          initial_indent=indent,
                          subsequent_indent=indent),
        ])
    return '%s\n\n%s' % (usage, '\n'.join(parts))

def main():
    parser = optparse.OptionParser(usage=makeHelp([]))
    config.toOptionParser(parser=parser)
    parser.disable_interspersed_args() # For future support of commands with args.
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('-'):
        configFilename = sys.argv.pop(1)
        try:
            fp = open(configFilename)
        except EnvironmentError, e:
            util.error('Could not open configuration file %r: %s' % (configFilename, e))
        
        config.read(configFilename)
        config.readenv()
        #config.writefp(sys.stdout)

        cmds = [getattr(commands, name)(config) for name in commands.commands]
        for child in config.commands.arbitrary.children():
            cmds.append(commands.ArbitraryCommand(config, name))
        parser.set_usage(makeHelp(cmds, configFilename))
    else:
        parser.error('A configuration file must be provided.')

    (options, args) = parser.parse_args()
    try:
        commandName = args.pop(0)
    except (ValueError, IndexError): # Unpack list of wrong size
        parser.error('A command must be provided.')

    if configFilename.startswith('/'):
        absoluteConfigFilename = configFilename
    else:
        absoluteConfigFilename = os.path.join(os.getcwd(), configFilename)
    syslog.openlog('%s %s' % (os.path.basename(sys.argv[0]), absoluteConfigFilename))


    try:
        (command,) = [cmd for cmd in cmds if cmd.name == commandName]
    except ValueError: # unpack list of wrong size
        parser.error('Invalid command: %r' % commandName)

    try:
        command.checkConfig(config)
    except commands.InvalidConfiguration, e:
        util.error('Invalid configuration: %s' % e)

    environ = makeEnvironment(config)
    command.run(args, environ)

if __name__ == '__main__':
    main()
