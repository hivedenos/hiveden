import subprocess

from hiveden.pkgs.base import PackageManager


class ArchPackageManager(PackageManager):
    def list_installed(self):
        result = subprocess.run(["pacman", "-Q"], capture_output=True, text=True)
        return result.stdout.strip().split('\n')

    def install(self, package):
        subprocess.run(["pacman", "-S", "--noconfirm", package], check=True)

    def remove(self, package):
        subprocess.run(["pacman", "-R", "--noconfirm", package], check=True)

    def search(self, package):
        result = subprocess.run(["pacman", "-Ss", package], capture_output=True, text=True)
        return result.stdout.strip().split('\n')

    def get_install_command(self, package: str) -> str:
        return f"pacman -S --noconfirm {package}"

    def get_check_installed_command(self, package: str) -> str:
        return f"pacman -Q {package}"


