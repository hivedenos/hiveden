from abc import ABC, abstractmethod


class PackageManager(ABC):
    @abstractmethod
    def list_installed(self):
        pass

    @abstractmethod
    def install(self, package):
        pass

    @abstractmethod
    def remove(self, package):
        pass

    @abstractmethod
    def search(self, package):
        pass

    @abstractmethod
    def get_install_command(self, package: str) -> str:
        pass

    @abstractmethod
    def get_check_installed_command(self, package: str) -> str:
        pass


