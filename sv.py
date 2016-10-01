#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2016 Dino Occhialini <dino.occhialini@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

DOCUMENTATION = '''
---
module: sv
short_description: Manage services with sv
description:
    - Manage services on runnit with sv.
author:
    - "Dino Occhialini (@dinoocch)"
notes: []
requirements: []
version_added: 2.2
options:
    name:
        description: Name of the service
        required: yes
        default: None
    enabled:
        description: If the service should be enabled.
        required: no
        choices: ["yes", "no"]
    state:
        description: Service state
        required: no
        choices: ["started", "stopped", "restarted", "reloaded"]
'''

EXAMPLES = '''
# Ensure httpd is started (implies enabled)
- service: name=httpd state=started

# Restart httpd (implies enabled)
- service: name=httpd state=restarted

# Ensure httpd is stopped (stops if enabled)
- service: name=httpd state=stopped

# Reload httpd (implies enabled)
- service: name=httpd state=reloaded
'''

RETURN = '''
msg:
    description: Message about results
    returned: success
    type: string
    sample: "httpd restarted"
'''


import os
import time

class Service(object):
    platform = 'Void Linux'
    distribution = None

    def __init__(self, module, sv_path):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.enable = module.params['enabled']
        self.changed = False
        self.running = None
        self.action = None

        self.sv_path = sv_path

    def get_enabled(self):
        """ Check if service is enabled.
        Returns True if link exists, False otherwise"""

        src = os.path.join("/", "var", "service", self.name)
        if os.path.islink(src):
            self.module.debug("Service is currently enabled")
            return True
        else:
            self.module.debug("Service is currently disabled")
            return False

    def do_enable(self):
        """ Enable service by creating a symlink."""
        if self.get_enabled():
            return (True, 'Already enabled.')

        self.changed = True
        self.module.debug("Would enable.")
        if self.module.check_mode:
            return (True, 'Would be enabled.')

        src = os.path.join("/", "etc", "sv", self.name)
        dest = os.path.join("/", "var", "service", self.name)
        try:
            os.symlink(src, dest)
            self.module.debug("Enabled service")
            return (True, '')
        except OSError, e:
            self.module.fail_json(msg=e.strerror)

    def do_disable(self):
        """ Disable service by deleting symlink """
        if not self.get_enabled():
            return (True, 'Already disabled.')

        self.changed = True
        self.module.debug("Would disable.")
        if self.module.check_mode:
            return (True, 'Would be disabled.')

        src = os.path.join("/", "var", "service", self.name)

        try:
            os.unlink(src)
            self.module.debug("Disabled service")
            return (True, 'Disabled.')
        except OSError, e:
            self.module.fail_json(msg=e.strerror)

    def get_status(self):
        """ Get service status using sv """

        if not self.get_enabled():
            self.running = False
            return "disabled"
        cmd = "%s status %s" % (self.sv_path, self.name)

        rc, stdout, stderr = self.module.run_command(cmd, check_rc=False)

        if rc != 0:
            self.module.fail_json(msg=stdout)

        status = stdout.split(":")[0]
        self.module.debug("Status %s" % status)
        if status not in ["run", "down"]:
            self.module.fail_json(msg="Invalid status. Will not proceed.")
        if status == "run":
            self.running = True
            return "up"
        else:
            self.running = False
            return "down"

    def change_sv(self, action):
        """ Do action based on current state """
        if action == "restart" or \
           (self.running is False and action in ['start', 'restart', 'reload'])\
           or (self.running is True and action == 'stop'):
            self.changed = True
        else:
            return False, 'Nothing to do.'

        if self.module.check_mode:
            return True, 'Would be changed.'

        if action == "restart" and self.running is True:
            cmd = "sv restart %s" % self.name
        elif action == "restart" or action == "start":
            cmd = "sv start %s" % self.name
        elif action == "stop":
            cmd = "sv stop %s" % self.name
        elif action == "reload" and self.running is False:
            cmd = "sv start %s" % self.name
        elif action == "reload":
            cmd = "sv hup %s" % self.name

        self.module.debug(cmd)
        rc, stdout, stderr = self.module.run_command(cmd, check_rc=False)

        if rc != 0:
            self.module.fail_json(msg=stderr)

    def do_action(self):
        if self.enable is True:
            self.do_enable()
            if self.changed:
                time.sleep(1)
            self.get_status()
            self.change_sv(self.state[:-2])
        else:
            if self.get_enabled():
                self.change_sv("stop")
            self.do_disable()


def main():
    """Returns, calling appropriate command"""

    mask = os.umask(0)  # fix the umask

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(aliases=['name', 'service']),
            state=dict(default=None, choices=['started', 'restarted',
                                              'stopped', 'reloaded']),
            enabled=dict(default=None, type='bool')
        ),
        required_one_of=[['state', 'enabled']],
        supports_check_mode=True)

    p = module.params

    # Set path for sv
    sv_path = module.get_bin_path('sv', True)
    if not os.path.exists(sv_path):
        module.fail_json(msg="Cannot find sv binary in path.")

    # ensure enabled if required
    if p['state'] in ['started', 'restarted', 'reload']:
        if p['enabled'] is False:
            module.fail_json(msg="Conflicting request. Will not proceed.")
        p['enabled'] = True

    if p['enabled'] is False:
        if not p['state'] is None and p['state'] != "stopped":
            module.fail_json(msg="Conflicting request. Will not proceed.")
        p['state'] = "stopped"

    service = Service(module, sv_path)
    module.debug("Service initialized.")
    service.do_action()

    result = {}
    result["name"] = service.name
    result["changed"] = service.changed
    result["enable"] = service.get_enabled()
    result["state"] = "down" if not result["enable"] else service.get_status()

    module.exit_json(**result)
    os.umask(mask)  # Reset the umask to original value

# import module snippets
from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
