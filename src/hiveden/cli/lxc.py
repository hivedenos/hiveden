import click

@click.group()
@click.pass_context
def lxc(ctx):
    """LXC container management commands"""
    from hiveden.lxc.containers import check_lxc_support
    try:
        check_lxc_support()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.abort()

@lxc.command(name='list')
def list_lxc_containers():
    """List all LXC containers."""
    from hiveden.lxc.containers import list_containers
    containers = list_containers()
    for c in containers:
        click.echo(f"{c.name} - {c.state}")

@lxc.command()
@click.argument('name')
@click.option('--template', default='ubuntu', help='The template to use.')
def create_lxc_container(name, template):
    """Create a new LXC container."""
    from hiveden.lxc.containers import create_container
    try:
        create_container(name, template)
        click.echo(f"Container '{name}' created.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@lxc.command()
@click.argument('name')
def start_lxc_container(name):
    """Start an LXC container."""
    from hiveden.lxc.containers import start_container
    try:
        start_container(name)
        click.echo(f"Container '{name}' started.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@lxc.command()
@click.argument('name')
def stop_lxc_container(name):
    """Stop an LXC container."""
    from hiveden.lxc.containers import stop_container
    try:
        stop_container(name)
        click.echo(f"Container '{name}' stopped.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@lxc.command()
@click.argument('name')
def delete_lxc_container(name):
    """Delete an LXC container."""
    from hiveden.lxc.containers import delete_container
    try:
        delete_container(name)
        click.echo(f"Container '{name}' deleted.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
