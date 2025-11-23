import click
import json

@click.group()
@click.pass_context
def info(ctx):
    """Get OS and hardware information."""
    pass

@info.command(name='os')
def get_os():
    """Get OS information."""
    from hiveden.hwosinfo.os import get_os_info
    click.echo(json.dumps(get_os_info(), indent=4))

@info.command(name='hw')
def get_hw():
    """Get hardware information."""
    from hiveden.hwosinfo.hw import get_hw_info
    click.echo(json.dumps(get_hw_info(), indent=4))
