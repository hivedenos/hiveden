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
