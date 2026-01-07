import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from hiveden.api.routers.system import get_comprehensive_locations
from hiveden.explorer.models import FilesystemLocation

class TestLocationsTree(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.apps_dir = os.path.join(self.test_dir, "apps")
        os.makedirs(self.apps_dir)
        
        # Create structure:
        # apps/
        #   app1/
        #     config/
        #   app2/
        
        os.makedirs(os.path.join(self.apps_dir, "app1", "config"))
        os.makedirs(os.path.join(self.apps_dir, "app2"))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('hiveden.api.routers.system.get_db_manager')
    @patch('hiveden.api.routers.system.LocationRepository')
    @patch('hiveden.shares.btrfs.BtrfsManager')
    def test_get_comprehensive_locations(self, mock_btrfs_cls, mock_repo_cls, mock_get_db):
        # Mock Btrfs
        mock_btrfs = mock_btrfs_cls.return_value
        mock_btrfs.list_shares.return_value = [
            MagicMock(name="share1", mount_path="/mnt/share1")
        ]
        # Fix the name attribute on the mock object itself since name is a special arg to MagicMock
        mock_btrfs.list_shares.return_value[0].name = "share1"

        # Mock DB Locations
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_system_locations.return_value = [
            FilesystemLocation(label="Apps", name="Apps", path=self.apps_dir, key="apps", type="system"),
            FilesystemLocation(label="Movies", name="Movies", path="/mnt/movies", key="movies", type="system")
        ]

        # Call function
        # We need to patch the import inside the function or ensure it uses the mocked modules
        # Since I patched the modules where they are imported in system.py, it should work.
        # Wait, the function imports BtrfsManager inside. patch should handle 'hiveden.shares.btrfs.BtrfsManager'
        
        # Note: function imports: from hiveden.shares.btrfs import BtrfsManager
        # So patching hiveden.shares.btrfs.BtrfsManager should work.
        
        response = get_comprehensive_locations()
        locations = response.data
        
        # Verify
        # 1. Btrfs Share
        self.assertTrue(any(l.label == "share1" and l.type == "share_btrfs" for l in locations))
        
        # 2. System Locations
        self.assertTrue(any(l.label == "Apps" and l.key == "apps" for l in locations))
        self.assertTrue(any(l.label == "Movies" and l.key == "movies" for l in locations))
        
        # 3. Apps Expansion Level 1
        self.assertTrue(any(l.label == "app1" and l.type == "app_directory" for l in locations))
        self.assertTrue(any(l.label == "app2" and l.type == "app_directory" for l in locations))
        
        # 4. Apps Expansion Level 2
        self.assertTrue(any(l.label == "app1/config" and l.type == "app_subdirectory" for l in locations))

if __name__ == "__main__":
    unittest.main()
