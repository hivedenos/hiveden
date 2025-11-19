import os

from hiveden.pkgs.arch import ArchPackageManager
from hiveden.pkgs.debian import DebianPackageManager
from hiveden.pkgs.fedora import FedoraPackageManager


def get_distro():
    if not os.path.exists("/etc/os-release"):
        return None
    with open("/etc/os-release") as f:
        for line in f:
            if line.startswith("ID="):
                return line.split('=')[1].strip().replace('"', '')
    return None

def get_package_manager():
    distro = get_distro()
    if distro in ["arch"]:
        return ArchPackageManager()
    elif distro in ["debian", "ubuntu"]:
        return DebianPackageManager()
    elif distro in ["fedora", "centos", "rhel"]:
        return FedoraPackageManager()
    else:
        raise Exception(f"Unsupported distribution: {distro}")
