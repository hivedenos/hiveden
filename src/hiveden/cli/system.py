import click

@click.group()
@click.pass_context
def system(ctx):
    """System commands"""
    pass

@system.command(name='disks')
@click.option('--all', 'show_all', is_flag=True, help='Show all disks.')
@click.option('--free', 'show_free', is_flag=True, help='Show only free disks.')
def get_system_disks(show_all, show_free):
    """Show system disks."""
    from hiveden.hwosinfo.hw import get_disks
    disks = get_disks()

    if show_free:
        disks = [d for d in disks if d.get("fstype") is None and d.get("type") == 'disk']

    for disk in disks:
        click.echo(f"{disk['name']} - {disk.get('fstype', 'N/A')} - {disk['size']}")
