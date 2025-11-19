import click
import yaml


@click.group()
@click.option("--config", default="config.yaml", help="Path to the configuration file.")
@click.pass_context
def main(ctx, config):
    """Hiveden CLI"""
    ctx.ensure_object(dict)
    with open(config, "r") as f:
        ctx.obj["config"] = yaml.safe_load(f)


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


if __name__ == "__main__":
    main()
