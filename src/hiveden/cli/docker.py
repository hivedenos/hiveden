import click
import os
import yaml
from hiveden.cli.utils import MutuallyExclusiveOption

def get_docker_manager():
    from hiveden.docker.containers import DockerManager
    
    network_name = "hiveden-network"
    
    # Try to load config
    config_path = "config.yaml"
    if os.path.exists(os.path.expanduser("~/.config/hiveden/config.yaml")):
        config_path = os.path.expanduser("~/.config/hiveden/config.yaml")
    elif os.path.exists("/etc/hiveden/config.yaml"):
        config_path = "/etc/hiveden/config.yaml"
        
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config and "docker" in config and "network_name" in config["docker"]:
                    network_name = config["docker"]["network_name"]
        except Exception:
            pass # Fallback to default
            
    return DockerManager(network_name=network_name)


@click.group()
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
    manager = get_docker_manager()

    containers = manager.list_containers(all=True, only_managed=only_managed)
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

    manager = get_docker_manager()

    if not name and not id:
        raise click.UsageError("Either --name or --id must be provided.")

    try:
        container = manager.describe_container(container_id=id, name=name)
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
    manager = get_docker_manager()

    if not all_containers and not managed and not name:
        raise click.UsageError(
            "Either --all, --managed, or --name must be provided."
        )

    containers_to_stop = []
    if all_containers:
        containers_to_stop = manager.list_containers(all=True)
    elif managed:
        containers_to_stop = manager.list_containers(only_managed=True)
    elif name:
        containers_to_stop = manager.list_containers(names=[name])

    if not containers_to_stop:
        click.echo("No containers found to stop.")
        return

    manager.stop_containers(containers_to_stop)


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
    manager = get_docker_manager()

    if not all_containers and not managed and not name:
        raise click.UsageError(
            "Either --all, --managed, or --name must be provided."
        )

    containers_to_delete = []
    if all_containers:
        containers_to_delete = manager.list_containers(all=True)
    elif managed:
        containers_to_delete = manager.list_containers(only_managed=True)
    elif name:
        containers_to_delete = manager.list_containers(names=[name])

    if not containers_to_delete:
        click.echo("No containers found to delete.")
        return

    manager.delete_containers(containers_to_delete)
