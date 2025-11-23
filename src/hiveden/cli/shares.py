import click

@click.group()
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


@shares.group()
def samba():
    """Manage Samba shares."""
    pass

@samba.command(name="check")
def check_samba():
    """Check if Samba is installed."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    if manager.check_installed():
        click.echo("Samba is installed.")
    else:
        click.echo("Samba is NOT installed.")

@samba.command(name="install")
def install_samba():
    """Install Samba."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.install()
        click.echo("Samba installed successfully.")
    except Exception as e:
        click.echo(f"Error installing Samba: {e}", err=True)

@samba.command(name="list")
def list_samba_shares():
    """List Samba shares."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    shares = manager.list_shares()
    if not shares:
        click.echo("No shares found.")
        return
    
    for share in shares:
        click.echo(f"Name: {share['name']}")
        click.echo(f"  Path: {share['path']}")
        click.echo(f"  Comment: {share['comment']}")
        click.echo(f"  Read Only: {share['read_only']}")
        click.echo("-" * 20)

@samba.command(name="create")
@click.argument("name")
@click.argument("path")
@click.option("--comment", default="", help="Share comment")
@click.option("--readonly", is_flag=True, help="Set read only")
@click.option("--browsable/--no-browsable", default=True, help="Set browsable")
@click.option("--guest-ok", is_flag=True, help="Allow guest access")
def create_samba_share(name, path, comment, readonly, browsable, guest_ok):
    """Create a Samba share."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.create_share(name, path, comment, readonly, browsable, guest_ok)
        click.echo(f"Share '{name}' created.")
    except Exception as e:
        click.echo(f"Error creating share: {e}", err=True)

@samba.command(name="delete")
@click.argument("name")
def delete_samba_share(name):
    """Delete a Samba share."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.delete_share(name)
        click.echo(f"Share '{name}' deleted.")
    except Exception as e:
        click.echo(f"Error deleting share: {e}", err=True)

@samba.command(name="start")
def start_samba():
    """Start the Samba service."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.start_service()
        click.echo("Samba service started.")
    except Exception as e:
        click.echo(f"Error starting Samba: {e}", err=True)

@samba.command(name="stop")
def stop_samba():
    """Stop the Samba service."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.stop_service()
        click.echo("Samba service stopped.")
    except Exception as e:
        click.echo(f"Error stopping Samba: {e}", err=True)

@samba.command(name="restart")
def restart_samba():
    """Restart the Samba service."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    try:
        manager.restart_service()
        click.echo("Samba service restarted.")
    except Exception as e:
        click.echo(f"Error restarting Samba: {e}", err=True)

@samba.command(name="status")
def status_samba():
    """Get the status of the Samba service."""
    from hiveden.shares.smb import SMBManager
    manager = SMBManager()
    status = manager.get_status()
    click.echo(f"Samba service status: {status}")
