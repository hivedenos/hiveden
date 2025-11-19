import os

import lxc
from lxc import version


def check_lxc_support():
    """Check if the system can create LXC containers."""
    if not os.path.exists("/var/lib/lxc"):
        raise Exception("LXC not installed or not configured correctly.")
    if not version:
        raise Exception("LXC python bindings not working.")

def create_container(name, template="ubuntu", **kwargs):
    """Create a new LXC container."""
    check_lxc_support()
    c = lxc.Container(name)
    if c.defined:
        raise Exception(f"Container {name} already exists.")
    c.create(template, **kwargs)
    return c

def get_container(name):
    """Get an LXC container by its name."""
    check_lxc_support()
    c = lxc.Container(name)
    if not c.defined:
        raise Exception(f"Container {name} not found.")
    return c

def list_containers():
    """List all LXC containers."""
    check_lxc_support()
    return [lxc.Container(name) for name in lxc.list_containers()]

def start_container(name):
    """Start an LXC container."""
    c = get_container(name)
    c.start()
    return c

def stop_container(name):
    """Stop an LXC container."""
    c = get_container(name)
    c.stop()
    return c

def delete_container(name):
    """Delete an LXC container."""
    c = get_container(name)
    c.destroy()
