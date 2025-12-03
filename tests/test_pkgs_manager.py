import pytest
from unittest.mock import Mock, patch
from hiveden.pkgs.manager import get_system_required_packages
from hiveden.pkgs.models import RequiredPackage, PackageStatus, PackageOperation
from hiveden.pkgs.base import PackageManager

class MockPackageManager(PackageManager):
    def list_installed(self):
        return []
    def install(self, package):
        pass
    def remove(self, package):
        pass
    def search(self, package):
        return []
    def get_install_command(self, package):
        return f"install {package}"
    def get_check_installed_command(self, package):
        return f"check {package}"
    def is_installed(self, package):
        return package == "installed-pkg"
    def get_required_packages(self):
        return [
            RequiredPackage(name="installed-pkg", title="Installed Package", description="Description 1", operation=PackageOperation.INSTALL),
            RequiredPackage(name="missing-pkg", title="Missing Package", description="Description 2", operation=PackageOperation.UNINSTALL)
        ]

@patch('hiveden.pkgs.manager.get_package_manager')
def test_get_system_required_packages(mock_get_pm):
    mock_pm = MockPackageManager()
    mock_get_pm.return_value = mock_pm
    
    packages = get_system_required_packages()
    
    assert len(packages) == 2
    assert isinstance(packages[0], PackageStatus)
    assert packages[0].name == "installed-pkg"
    assert packages[0].installed is True
    assert packages[0].operation == PackageOperation.INSTALL
    assert packages[1].name == "missing-pkg"
    assert packages[1].installed is False
    assert packages[1].operation == PackageOperation.UNINSTALL
