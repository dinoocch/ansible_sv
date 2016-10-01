# ansible module for sv

Manage sv similar to built-in service module.

Currently, this is separate from service so that it may be used while a PR to
the service module is composed and potentially accepted.

## Requirements
* Ansible

## Options
```yml
name:
	description: Name of the service
	required: yes
	default: None
enabled:
	description: If the service should be enabled. Disabling the service stops it first.
	required: no
	choices: ["yes", "no"]
state:
	description: Service state (service must be enabled, therefore this implies enabled)
	required: no
	choices: ["started", "stopped", "restarted", "reloaded"]
```

## EXAMPLES
```yml
- service: name=httpd state=started

- service: name=httpd state=restarted

- service: name=httpd state=stopped

- service: name=httpd state=stopped
```

## Authors:
* "Dino Occhialini (@dinoocch)"
