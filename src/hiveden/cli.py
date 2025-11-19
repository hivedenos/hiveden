import os

import click
import yaml


@click.group()
@click.option('--config', help='Path to the configuration file.')
@click.pass_context
def main(ctx, config):
    """Hiveden CLI"""
    ctx.ensure_object(dict)
    if config:
        config_path = config
    elif os.path.exists('config.yaml'):
        config_path = 'config.yaml'
    elif os.path.exists(os.path.expanduser('~/.config/hiveden/config.yaml')):
        config_path = os.path.expanduser('~/.config/hiveden/config.yaml')
    elif os.path.exists('/etc/hiveden/config.yaml'):
        config_path = '/etc/hiveden/config.yaml'
    else:
        raise click.FileError('Configuration file not found.')

    with open(config_path, 'r') as f:
        ctx.obj['config'] = yaml.safe_load(f)


@main.group()
@click.pass_context
def docker(ctx):
    """Docker commands"""
    pass


@docker.command(name="list-containers")
@click.pass_context
def list_containers(ctx):
    """List all docker containers."""
    from hiveden.docker.containers import list_containers

    containers = list_containers(all=True)
    for container in containers:
        click.echo(f"{container.name} - {container.image.id} - {container.status}")


@docker.command()
@click.pass_context
def apply(ctx):
    """Apply the docker configuration."""
    from docker import errors

    from hiveden.docker.containers import create_container, list_containers

    config = ctx.obj["config"]["docker"]
    network_name = config["network_name"]

    # Create containers
    for container_config in config["containers"]:
        container_name = container_config["name"]
        image = container_config["image"]
        try:
            containers = list_containers(all=True, filters={"name": container_name})
            if not containers:
                create_container(
                    image=image,
                    name=container_name,
                    detach=True,
                    network_name=network_name,
                )
                click.echo(
                    f"Container '{container_name}' created and connected to '{network_name}'."
                )
            else:
                click.echo(f"Container '{container_name}' already exists.")
        except errors.ImageNotFound:
            click.echo(
                f"Image '{image}' not found for container '{container_name}'.", err=True
            )
        except errors.APIError as e:
            click.echo(f"Error creating container '{container_name}': {e}", err=True)


@docker.command()
@click.pass_context
def hello(ctx):
    """Prints the docker config."""
    click.echo(ctx.obj["config"]["docker"])


@main.group()
@click.pass_context
def pkgs(ctx):
    """Package management commands"""
    from hiveden.pkgs.manager import get_package_manager
    ctx.obj['pm'] = get_package_manager()

@pkgs.command(name='list')
@click.pass_context
def list_packages(ctx):
    """List all installed packages."""
    packages = ctx.obj['pm'].list_installed()
    for package in packages:
        click.echo(package)

@pkgs.command()
@click.argument('package')
@click.pass_context
def install_package(ctx, package):
    """Install a package."""
    ctx.obj['pm'].install(package)
    click.echo(f"Package '{package}' installed.")

@pkgs.command()
@click.argument('package')
@click.pass_context
def remove_package(ctx, package):
    """Remove a package."""
    ctx.obj['pm'].remove(package)
    click.echo(f"Package '{package}' removed.")

@pkgs.command()
@click.argument('package')
@click.pass_context
def search_package(ctx, package):
    """Search for a package."""
    packages = ctx.obj['pm'].search(package)
    for p in packages:
        click.echo(p)

@main.group()
@click.pass_context
def info(ctx):
    """Get OS and hardware information."""
    pass

@info.command(name='os')
def get_os():
    """Get OS information."""
    import json

    from hiveden.hwosinfo.os import get_os_info
    click.echo(json.dumps(get_os_info(), indent=4))

@info.command(name='hw')
def get_hw():
    """Get hardware information."""
    import json

    from hiveden.hwosinfo.hw import get_hw_info
    click.echo(json.dumps(get_hw_info(), indent=4))

@main.group()
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


@main.command()
@click.option('--host', default='127.0.0.1', help='The host to bind to.')
@click.option('--port', default=8000, help='The port to bind to.')
def server(host, port):
    """Run the FastAPI server."""
    import uvicorn

    from hiveden.api.server import app
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
