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

@info.command(name='devices')
def get_devices():
    """Get all system devices."""
    from hiveden.hwosinfo.devices import get_all_devices
    # Use Pydantic's model_dump/dict
    devices = get_all_devices()
    # Check for pydantic v2 model_dump, else dict()
    if hasattr(devices, "model_dump"):
        data = devices.model_dump()
    else:
        data = devices.dict()
    click.echo(json.dumps(data, indent=4, default=str))