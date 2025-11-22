import os

import click
import yaml


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive)
            kwargs["help"] = help + (
                " NOTE: This option is mutually exclusive with "
                " options: [%s]." % ex_str
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `%s` is mutually exclusive with "
                " `%s`." % (self.name, ", ".join(self.mutually_exclusive))
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)


@click.group()
@click.pass_context
def main(ctx):
    """Hiveden CLI"""
    ctx.ensure_object(dict)


@main.group()
@click.pass_context
def docker(ctx):
    """Docker commands"""
    pass


@docker.command(name="list-containers")
@click.option(
    "--only-managed", is_flag=True, help="List only containers managed by hiveden."
)
@click.pass_context
def list_containers(ctx, only_managed):
    """List all docker containers."""
    from hiveden.docker.containers import list_containers

    containers = list_containers(all=True, only_managed=only_managed)
    for container in containers:
        name = container.Names[0] if container.Names else "N/A"
        click.echo(f"{name} - {container.Image} - {container.Status}")


@docker.command(name="describe-container")
@click.option(
    "--name",
    "name",
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["id"],
    help="The name of the container.",
)
@click.option(
    "--id",
    "id",
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["name"],
    help="The ID of the container.",
)
def describe_container(name, id):
    """Describe a docker container."""
    from docker.errors import NotFound

    from hiveden.docker.containers import describe_container as describe

    if not name and not id:
        raise click.UsageError("Either --name or --id must be provided.")

    try:
        container = describe(container_id=id, name=name)
        for key, value in container:
            click.echo(f"{key}: {value}")
    except NotFound as e:
        raise click.ClickException(e.explanation or 'Strange Exception. Talk to the developers to maybe know more.')


@docker.command(name="stop-container")
@click.option(
    "--all",
    "all_containers",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["managed", "name"],
    help="Stop all containers.",
)
@click.option(
    "--managed",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["all_containers", "name"],
    help="Stop only containers managed by hiveden.",
)
@click.option(
    "--name",
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["all_containers", "managed"],
    help="The name of the container to stop.",
)
def stop_container(all_containers, managed, name):
    """Stop docker containers."""
    from hiveden.docker.containers import list_containers, stop_containers

    if not all_containers and not managed and not name:
        raise click.UsageError(
            "Either --all, --managed, or --name must be provided."
        )

    containers_to_stop = []
    if all_containers:
        containers_to_stop = list_containers(all=True)
    elif managed:
        containers_to_stop = list_containers(only_managed=True)
    elif name:
        containers_to_stop = list_containers(names=[name])

    if not containers_to_stop:
        click.echo("No containers found to stop.")
        return

    stop_containers(containers_to_stop)


@docker.command(name="delete-container")
@click.option(
    "--all",
    "all_containers",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["managed", "name"],
    help="Delete all containers.",
)
@click.option(
    "--managed",
    is_flag=True,
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["all_containers", "name"],
    help="Delete only containers managed by hiveden.",
)
@click.option(
    "--name",
    cls=MutuallyExclusiveOption,
    mutually_exclusive=["all_containers", "managed"],
    help="The name of the container to delete.",
)
def delete_container(all_containers, managed, name):
    """Delete docker containers."""
    from hiveden.docker.containers import delete_containers, list_containers

    if not all_containers and not managed and not name:
        raise click.UsageError(
            "Either --all, --managed, or --name must be provided."
        )

    containers_to_delete = []
    if all_containers:
        containers_to_delete = list_containers(all=True)
    elif managed:
        containers_to_delete = list_containers(only_managed=True)
    elif name:
        containers_to_delete = list_containers(names=[name])

    if not containers_to_delete:
        click.echo("No containers found to delete.")
        return

    delete_containers(containers_to_delete)


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


@main.group()
def shares():
    """Manage shares."""
    pass

@shares.group()
def zfs():
    """Manage ZFS shares."""
    pass

@zfs.command("list-pools")
def list_zfs_pools():
    """List ZFS pools."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    pools = manager.list_pools()
    for pool in pools:
        click.echo(pool)

@zfs.command("create-pool")
@click.argument("name")
@click.argument("devices", nargs=-1)
def create_zfs_pool(name, devices):
    """Create a ZFS pool."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    manager.create_pool(name, list(devices))
    click.echo(f"Pool '{name}' created.")

@zfs.command("destroy-pool")
@click.argument("name")
def destroy_zfs_pool(name):
    """Destroy a ZFS pool."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    manager.destroy_pool(name)
    click.echo(f"Pool '{name}' destroyed.")

@zfs.command("list-datasets")
@click.argument("pool")
def list_zfs_datasets(pool):
    """List ZFS datasets."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    datasets = manager.list_datasets(pool)
    for dataset in datasets:
        click.echo(dataset)

@zfs.command("create-dataset")
@click.argument("name")
def create_zfs_dataset(name):
    """Create a ZFS dataset."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    manager.create_dataset(name)
    click.echo(f"Dataset '{name}' created.")

@zfs.command("destroy-dataset")
@click.argument("name")
def destroy_zfs_dataset(name):
    """Destroy a ZFS dataset."""
    from hiveden.shares.zfs import ZFSManager
    manager = ZFSManager()
    manager.destroy_dataset(name)
    click.echo(f"Dataset '{name}' destroyed.")

@zfs.command("list-available-devices")
def list_available_devices():
    """List available devices for ZFS pools."""
    from hiveden.hwosinfo.hw import get_available_devices
    devices = get_available_devices()
    for device in devices:
        click.echo(device)


@main.group()
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
