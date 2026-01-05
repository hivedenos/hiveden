import click
import os
import yaml

from hiveden.cli.docker import docker
from hiveden.cli.lxc import lxc
from hiveden.cli.pkgs import pkgs
from hiveden.cli.info import info
from hiveden.cli.shares import shares
from hiveden.cli.system import system
from hiveden.cli.apps_cli import apps

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
main.add_command(apps)

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
@click.option('--db-url', help='The database URL. Defaults to environment variables.')
def server(host, port, db_url):
    """Run the FastAPI server."""
    import logging
    import uvicorn
    from hiveden.bootstrap.manager import bootstrap_infrastructure, bootstrap_data
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Bootstrap Infrastructure (Directories, Core Containers like DB)
    bootstrap_infrastructure()
    
    if db_url:
        os.environ["HIVEDEN_DB_URL"] = db_url

    # 2. Bootstrap Data (Migrations, DB-dependent logic)
    # This will internally wait for DB to be ready
    bootstrap_data()

    from hiveden.api.server import app
    uvicorn.run(app, host=host, port=port, log_level="debug")

