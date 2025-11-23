import click
import os
import yaml
from hiveden.apps.pihole import PiHoleManager

def get_pihole_config():
    # Load config to find pihole credentials
    config_path = "config.yaml" # default
    if os.path.exists(os.path.expanduser("~/.config/hiveden/config.yaml")):
        config_path = os.path.expanduser("~/.config/hiveden/config.yaml")
    elif os.path.exists("/etc/hiveden/config.yaml"):
        config_path = "/etc/hiveden/config.yaml"
    
    if not os.path.exists(config_path):
        raise click.FileError("Configuration file not found.")
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    if 'apps' not in config or 'pihole' not in config['apps']:
        raise click.UsageError("Pi-hole configuration not found in config.yaml")
        
    pihole_conf = config['apps']['pihole']
    if 'host' not in pihole_conf or 'password' not in pihole_conf:
         raise click.UsageError("Pi-hole host or password missing in config.")
         
    docker_network = config.get('docker', {}).get('network_name', 'hiveden-network')
         
    return pihole_conf['host'], pihole_conf['password'], docker_network


@click.group()
def apps():
    """Manage apps."""
    pass

@apps.group()
def pihole():
    """Manage Pi-hole."""
    pass

@pihole.group(name='dns')
def dns_entries():
    """Manage DNS entries."""
    pass

@dns_entries.command(name='list')
def list_dns():
    """List DNS entries."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    entries = mgr.list_dns_entries()
    for entry in entries:
        click.echo(f"{entry['domain']} -> {entry['ip']}")

@dns_entries.command(name='add')
@click.argument('domain')
@click.argument('ip')
def add_dns(domain, ip):
    """Add DNS entry."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.add_dns_entry(domain, ip)
    click.echo(f"Added {domain} -> {ip}")

@dns_entries.command(name='delete')
@click.argument('domain')
@click.argument('ip')
def delete_dns(domain, ip):
    """Delete DNS entry."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.delete_dns_entry(domain, ip)
    click.echo(f"Deleted {domain} -> {ip}")


@pihole.group(name='block')
def block():
    """Manage Blocklist."""
    pass

@block.command(name='list')
def list_block():
    """List blocked domains."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    domains = mgr.list_blacklist()
    for d in domains:
        click.echo(d['domain'])

@block.command(name='add')
@click.argument('domain')
def add_block(domain):
    """Block a domain."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.add_to_blacklist(domain)
    click.echo(f"Blocked {domain}")

@block.command(name='remove')
@click.argument('domain')
def remove_block(domain):
    """Unblock a domain."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.remove_from_blacklist(domain)
    click.echo(f"Unblocked {domain}")


@pihole.group(name='whitelist')
def whitelist():
    """Manage Whitelist."""
    pass

@whitelist.command(name='list')
def list_whitelist():
    """List whitelisted domains."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    domains = mgr.list_whitelist()
    for d in domains:
        click.echo(d['domain'])

@whitelist.command(name='add')
@click.argument('domain')
def add_whitelist(domain):
    """Whitelist a domain."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.add_to_whitelist(domain)
    click.echo(f"Whitelisted {domain}")

@whitelist.command(name='remove')
@click.argument('domain')
def remove_whitelist(domain):
    """Remove from whitelist."""
    host, password, network = get_pihole_config()
    mgr = PiHoleManager(host, password, docker_network_name=network)
    mgr.remove_from_whitelist(domain)
    click.echo(f"Removed {domain} from whitelist")
