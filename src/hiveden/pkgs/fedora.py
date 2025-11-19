import shutil
import subprocess

from hiveden.pkgs.base import PackageManager


class FedoraPackageManager(PackageManager):
    def __init__(self):
        if shutil.which("dnf"):
            self.pm = "dnf"
        elif shutil.which("yum"):
            self.pm = "yum"
        else:
            raise Exception("No package manager found (dnf or yum)")

    def list_installed(self):
        result = subprocess.run([self.pm, "list", "installed"], capture_output=True, text=True)
        return result.stdout.strip().split('\n')

    def install(self, package):
        subprocess.run([self.pm, "install", "-y", package], check=True)

    def remove(self, package):
        subprocess.run([self.pm, "remove", "-y", package], check=True)

    def search(self, package):
        result = subprocess.run([self.pm, "search", package], capture_output=True, text=True)
        return result.stdout.strip().split('\n')
