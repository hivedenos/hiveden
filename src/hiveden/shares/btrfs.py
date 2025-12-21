import os
import subprocess
from typing import List, Optional
import psutil
import json
from hiveden.api.dtos import BtrfsVolume, BtrfsShare

class BtrfsManager:
    def list_volumes(self) -> List[BtrfsVolume]:
        """
        List all mounted Btrfs volumes.
        """
        volumes = []
        for part in psutil.disk_partitions(all=False):
            if part.fstype == "btrfs":
                # Try to get label using lsblk if possible, but keep it simple for now
                volumes.append(BtrfsVolume(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    label=os.path.basename(part.mountpoint) # fallback label
                ))
        return volumes

    def list_shares(self) -> List[BtrfsShare]:
        """
        Lists all managed Btrfs subvolume shares by parsing /etc/fstab.
        """
        shares = []
        try:
            with open("/etc/fstab", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): # Skip empty lines and comments
                        continue
                    
                    parts = line.split()
                    # Expecting: device mount_path fstype options dump fsck
                    if len(parts) >= 6 and parts[2] == "btrfs":
                        device_spec = parts[0]
                        mount_path = parts[1]
                        options_str = parts[3]
                        
                        # Resolve UUID=... to actual device path
                        device = device_spec
                        if device_spec.startswith("UUID="):
                            uuid = device_spec.split("=")[1]
                            try:
                                # findfs UUID=... returns the device path
                                result = subprocess.run(
                                    ["findfs", device_spec],
                                    capture_output=True, text=True, check=True
                                )
                                device = result.stdout.strip()
                            except subprocess.CalledProcessError:
                                # Fallback or skip if device not found
                                pass
                        elif device_spec.startswith("/dev/disk/by-uuid/"):
                             # Resolve symlink to real device
                             try:
                                 device = os.path.realpath(device_spec)
                             except Exception:
                                 pass

                        subvolid = None
                        subvol_name = None

                        # Extract subvolid or subvol name from options
                        options = options_str.split(",")
                        for opt in options:
                            if opt.startswith("subvolid="):
                                subvolid = opt.split("=")[1]
                            elif opt.startswith("subvol="):
                                subvol_name = opt.split("=")[1]
                        
                        if not subvolid and not subvol_name: # Not a subvolume mount
                            continue
                        
                        # If subvol_name is available, use it. Otherwise, try to get from subvolid.
                        # If only subvolid, we still need the subvolume name for the BtrfsShare model.
                        # We can get it from 'btrfs subvolume show <mount_path>'
                        if not subvol_name and subvolid:
                             try:
                                show_result = subprocess.run(
                                    ["btrfs", "subvolume", "show", mount_path],
                                    capture_output=True, text=True, check=True
                                )
                                for show_line in show_result.stdout.splitlines():
                                    if "Name:" in show_line:
                                        subvol_name = show_line.split(":", 1)[1].strip()
                                        break
                             except Exception:
                                 pass # If fails, subvol_name remains None
                        
                        if not subvol_name:
                             # Fallback to basename of mount path if name cannot be determined
                             subvol_name = os.path.basename(mount_path)

                        # Find the root Btrfs mountpoint for the device
                        parent_path = self._get_btrfs_root_mountpoint(device)
                        
                        shares.append(BtrfsShare(
                            name=subvol_name,
                            parent_path=parent_path, # Can be None now
                            mount_path=mount_path,
                            device=device,
                            subvolid=subvolid if subvolid else "unknown" # subvolid should be present if mounted with it
                        ))
        except FileNotFoundError:
            pass # /etc/fstab not found, return empty list
        except Exception as e:
            # Log unexpected errors
            print(f"Error reading /etc/fstab for Btrfs shares: {e}")
        return shares

    def create_share(self, parent_path: str, name: str, mount_path: str):
        """
        Creates a Btrfs subvolume and mounts it.
        """
        # 1. Validate parent path is a btrfs mount
        if not self._is_btrfs(parent_path):
            raise ValueError(f"{parent_path} is not a Btrfs volume")

        # 2. Create Subvolume
        full_subvol_path = os.path.join(parent_path, name)
        if os.path.exists(full_subvol_path):
            raise ValueError(f"Subvolume or path {full_subvol_path} already exists")

        subprocess.run(["btrfs", "subvolume", "create", full_subvol_path], check=True)

        # 3. Create Mount Point
        os.makedirs(mount_path, exist_ok=True)

        # 4. Mount Subvolume
        # Need to find device for parent_path
        device = self._get_device_for_path(parent_path)
        
        # Get UUID for the device
        uuid = self._get_uuid_for_device(device)
        
        # To make it robust:
        # We can mount using subvolid if we fetch it.
        subvol_id = self._get_subvol_id(full_subvol_path)
        
        subprocess.run(
            ["mount", "-o", f"subvolid={subvol_id}", device, mount_path],
            check=True
        )

        # 5. Persist to fstab (simple append)
        # UUID=xxxx  mount_path  btrfs  subvolid=X,defaults  0  0
        # Note: Using UUID is more stable than device path
        device_spec = f"/dev/disk/by-uuid/{uuid}" if uuid else device
        fstab_entry = f"{device_spec} {mount_path} btrfs subvolid={subvol_id},defaults 0 0\n"
        with open("/etc/fstab", "a") as f:
            f.write(fstab_entry)

    def _is_btrfs(self, path: str) -> bool:
        """
        Check if path is a btrfs mountpoint.
        """
        for part in psutil.disk_partitions(all=True):
            if part.mountpoint == path and part.fstype == "btrfs":
                return True
        return False

    def _get_device_for_path(self, path: str) -> str:
        for part in psutil.disk_partitions(all=True):
            if part.mountpoint == path:
                return part.device
        raise ValueError(f"Device not found for path {path}")
    
    def _get_uuid_for_device(self, device: str) -> Optional[str]:
        """Get UUID for a block device."""
        try:
            # blkid -s UUID -o value <device>
            result = subprocess.run(
                ["blkid", "-s", "UUID", "-o", "value", device],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            return None

    def _get_subvol_id(self, path: str) -> str:
        # btrfs subvolume show <path> | grep "Subvolume ID:"
        result = subprocess.run(
            ["btrfs", "subvolume", "show", path],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if "Subvolume ID:" in line:
                return line.split(":")[-1].strip()
        raise ValueError(f"Could not determine Subvolume ID for {path}")

    def _get_btrfs_root_mountpoint(self, device: str) -> Optional[str]:
        """
        Finds the root mount point of a Btrfs filesystem given its device.
        This handles cases where the device is /dev/md0 or similar.
        """
        try:
            # Use findmnt to get all mounts. We cannot filter by SOURCE easily for /dev/md0 because 
            # findmnt output might be /dev/md0[/subvol].
            # Instead, we list all btrfs mounts and check if they match our device.
            result = subprocess.run(
                ["findmnt", "--raw", "--output", "TARGET,SOURCE,FSTYPE,OPTIONS", "--json"],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                filesystems = data.get("filesystems", [])
                
                for fs in filesystems:
                    if fs.get("FSTYPE") != "btrfs":
                        continue
                        
                    source = fs.get("SOURCE", "")
                    
                    # Check if source matches device. Source can be "/dev/md0" or "/dev/md0[/subvol]"
                    if source == device or source.startswith(f"{device}["):
                        options = fs.get("OPTIONS", "").split(',')
                        # Check for root subvolume indicators
                        # subvolid=5 is standard for top-level btrfs root
                        # subvol=/ is also a strong indicator
                        if "subvolid=5" in options or "subvol=/" in options:
                            return fs.get("TARGET")

            # Fallback to psutil if findmnt fails or doesn't find it (though findmnt is better for complex sources)
            for part in psutil.disk_partitions(all=False):
                if part.device == device and part.fstype == "btrfs":
                    # Check options in part.opts
                    opts = part.opts.split(',')
                    if "subvolid=5" in opts or "subvol=/" in opts:
                        return part.mountpoint
                    if not any(opt.startswith("subvol") for opt in opts):
                         return part.mountpoint
                         
        except Exception as e:
            print(f"Error finding root mountpoint for {device}: {e}")
            
        return None
