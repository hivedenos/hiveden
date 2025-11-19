import subprocess

from hiveden.pkgs.base import PackageManager


class DebianPackageManager(PackageManager):
    def list_installed(self):
        result = subprocess.run(["apt", "list", "--installed"], capture_output=True, text=True)
        return result.stdout.strip().split('\n')

    def install(self, package):
        subprocess.run(["apt-get", "install", "-y", package], check=True)

    def remove(self, package):
        subprocess.run(["apt-get", "remove", "-y", package], check=True)

    def search(self, package):
        result = subprocess.run(["apt-cache", "search", package], capture_output=True, text=True)
        return result.stdout.strip().split('\n')
