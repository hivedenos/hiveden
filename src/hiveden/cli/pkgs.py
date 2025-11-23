import click

@click.group()
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
