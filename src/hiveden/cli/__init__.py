import click
import os
import yaml

from hiveden.cli.docker import docker
from hiveden.cli.lxc import lxc
from hiveden.cli.pkgs import pkgs
from hiveden.cli.info import info
from hiveden.cli.shares import shares
from hiveden.cli.system import system

@click.group()
@click.pass_context
def main(ctx):
    """Hiveden CLI"""
    ctx.ensure_object(dict)

main.add_command(docker)
main.add_command(lxc)
main.add_command(pkgs)
main.add_command(info)
main.add_command(shares)
main.add_command(system)

@main.command()
@click.option("--config", help="Path to the configuration file.")
def apply(config):
    """Apply the configuration from a file."""
    if config:
        config_path = config
    elif os.path.exists("config.yaml"):
        config_path = "config.yaml"
    elif os.path.exists(os.path.expanduser("~/.config/hiveden/config.yaml")):
        config_path = os.path.expanduser("~/.config/hiveden/config.yaml")
    elif os.path.exists("/etc/hiveden/config.yaml"):
        config_path = "/etc/hiveden/config.yaml"
    else:
        raise click.FileError("Configuration file not found.")

    with open(config_path, "r") as f:
        full_config = yaml.safe_load(f)

    if "docker" in full_config:
        from hiveden.docker.actions import (
            apply_configuration as apply_docker_configuration,
        )

        messages = apply_docker_configuration(full_config["docker"])
        for message in messages:
            click.echo(message)


@main.command()
@click.option('--host', default='127.0.0.1', help='The host to bind to.')
@click.option('--port', default=8000, help='The port to bind to.')
def server(host, port):
    """Run the FastAPI server."""
    import uvicorn

    from hiveden.api.server import app
    uvicorn.run(app, host=host, port=port)
