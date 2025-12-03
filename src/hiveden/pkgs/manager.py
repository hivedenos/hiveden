from typing import List
from hiveden.hwosinfo.os import get_os_info
from hiveden.pkgs.arch import ArchPackageManager
from hiveden.pkgs.debian import DebianPackageManager
from hiveden.pkgs.fedora import FedoraPackageManager
from hiveden.pkgs.models import PackageStatus, RequiredPackage, PackageOperation


def get_package_manager():
    os_info = get_os_info()
    distro = os_info.get('id')
    if distro in ["arch"]:
        return ArchPackageManager()
    elif distro in ["debian", "ubuntu"]:
        return DebianPackageManager()
    elif distro in ["fedora", "centos", "rhel"]:
        return FedoraPackageManager()
    else:
        raise Exception(f"Unsupported distribution: {distro}")


def get_system_required_packages() -> List[PackageStatus]:
    pm = get_package_manager()
    packages = pm.get_required_packages()
    
    # Add storage related packages
    storage_packages = [
        RequiredPackage(
            name="mdadm",
            title="MDADM",
            description="Tool for managing Linux Software RAID arrays",
            operation=PackageOperation.INSTALL
        ),
        RequiredPackage(
            name="btrfs-progs",
            title="BTRFS Programs",
            description="Utilities for managing BTRFS filesystems",
            operation=PackageOperation.INSTALL
        ),
        RequiredPackage(
            name="parted",
            title="GNU Parted",
            description="Disk partitioning and partition resizing program",
            operation=PackageOperation.INSTALL
        ),
    ]
    
    # Combine lists
    all_required = packages + storage_packages
    
    # Check status for all
    return [
        PackageStatus(
            name=pkg.name,
            title=pkg.title,
            description=pkg.description,
            operation=pkg.operation,
            installed=pm.is_installed(pkg.name)
        )
        for pkg in all_required
    ]
