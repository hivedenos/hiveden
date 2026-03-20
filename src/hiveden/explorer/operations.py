import grp
import json
import logging
import mimetypes
import os
import pwd
import shutil
import stat
import subprocess
from datetime import datetime
from typing import Any, BinaryIO, Callable, List, Optional, Tuple

from hiveden.explorer.models import FileEntry, FileType, SortBy, SortOrder, USBDevice

logger = logging.getLogger(__name__)


class UploadCancelledError(Exception):
    pass


class ExplorerService:
    def __init__(self, root_directory: str = "/"):
        self.root_directory = os.path.abspath(root_directory)

    def _resolve_path(self, path: str) -> str:
        """
        Resolves path against root_directory and ensures it's safe.
        """
        if not path:
            return self.root_directory

        # Handle absolute paths that might not be rooted at root_directory in the FS view
        # But for this requirement, root_directory is likely "/" so all absolute paths are valid.
        # If root_directory was restricted (e.g. /home/user), we'd need to sandbox.
        # Assuming full system access for now based on context ("server management").

        return os.path.abspath(path)

    def _human_readable_size(self, size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _normalize_upload_path(self, filename: str) -> str:
        normalized = os.path.normpath(filename.replace("\\", "/"))
        if normalized in {"", ".", ".."}:
            raise ValueError("Invalid upload filename")
        if os.path.isabs(normalized):
            raise ValueError("Upload filename must be relative")

        parts = [part for part in normalized.split(os.sep) if part not in {"", "."}]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("Upload filename must stay within destination")

        return os.path.join(*parts)

    def resolve_upload_target_path(self, destination: str, filename: str) -> str:
        destination_dir = self._resolve_path(destination)
        relative_path = self._normalize_upload_path(filename)
        target_path = os.path.abspath(os.path.join(destination_dir, relative_path))

        if os.path.commonpath([destination_dir, target_path]) != destination_dir:
            raise ValueError("Upload filename must stay within destination")

        return target_path

    def _get_file_type(self, path: str, st: os.stat_result) -> FileType:
        if stat.S_ISDIR(st.st_mode):
            return FileType.DIRECTORY
        return FileType.FILE

    def _get_permissions_str(self, st: os.stat_result) -> str:
        return stat.filemode(st.st_mode)

    def _get_mime_type(self, path: str) -> Optional[str]:
        if os.path.isdir(path):
            return "inode/directory"
        mime, _ = mimetypes.guess_type(path)
        return mime or "application/octet-stream"

    def get_file_entry(self, path: str) -> FileEntry:
        st = os.stat(path, follow_symlinks=False)
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except KeyError:
            owner = str(st.st_uid)

        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            group = str(st.st_gid)

        is_symlink = stat.S_ISLNK(st.st_mode)
        symlink_target = os.readlink(path) if is_symlink else None

        return FileEntry(
            name=os.path.basename(path),
            path=path,
            type=self._get_file_type(path, st),
            size=st.st_size,
            size_human=self._human_readable_size(st.st_size),
            permissions=self._get_permissions_str(st),
            owner=owner,
            group=group,
            modified=datetime.fromtimestamp(st.st_mtime),
            accessed=datetime.fromtimestamp(st.st_atime),
            created=datetime.fromtimestamp(st.st_ctime),
            is_hidden=os.path.basename(path).startswith("."),
            is_symlink=is_symlink,
            symlink_target=symlink_target,
            mime_type=self._get_mime_type(path),
            permissions_octal=oct(st.st_mode)[-4:],
            owner_id=st.st_uid,
            group_id=st.st_gid,
            inode=st.st_ino,
            hard_links=st.st_nlink,
            is_readable=os.access(path, os.R_OK),
            is_writable=os.access(path, os.W_OK),
            is_executable=os.access(path, os.X_OK),
        )

    def list_directory(
        self,
        path: str,
        show_hidden: bool = False,
        sort_by: SortBy = SortBy.NAME,
        sort_order: SortOrder = SortOrder.ASC,
    ) -> Tuple[List[FileEntry], int, int]:
        abs_path = self._resolve_path(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Path not found: {path}")
        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        entries = []
        total_size = 0

        with os.scandir(abs_path) as it:
            for entry in it:
                if not show_hidden and entry.name.startswith("."):
                    continue

                try:
                    file_entry = self.get_file_entry(entry.path)
                    entries.append(file_entry)
                    if file_entry.type == FileType.FILE:
                        total_size += file_entry.size
                except (PermissionError, FileNotFoundError):
                    continue

        # Sorting
        reverse = sort_order == SortOrder.DESC
        if sort_by == SortBy.NAME:
            entries.sort(key=lambda x: x.name.lower(), reverse=reverse)
        elif sort_by == SortBy.SIZE:
            entries.sort(key=lambda x: x.size, reverse=reverse)
        elif sort_by == SortBy.MODIFIED:
            entries.sort(key=lambda x: x.modified or datetime.min, reverse=reverse)
        elif sort_by == SortBy.TYPE:
            entries.sort(key=lambda x: (x.type, x.name.lower()), reverse=reverse)

        return entries, len(entries), total_size

    def create_directory(self, path: str, parents: bool = False) -> str:
        abs_path = self._resolve_path(path)
        if os.path.exists(abs_path):
            raise FileExistsError(f"Path already exists: {path}")

        if parents:
            os.makedirs(abs_path, exist_ok=True)
        else:
            os.mkdir(abs_path)
        return abs_path

    def save_uploaded_file(
        self,
        destination: str,
        filename: str,
        file_obj: BinaryIO,
        size: Optional[int] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
        chunk_size: int = 1024 * 1024,
    ) -> FileEntry:
        if not filename:
            raise ValueError("Uploaded file is missing a filename")

        destination_dir = self._resolve_path(destination)
        if not os.path.exists(destination_dir):
            raise FileNotFoundError(f"Path not found: {destination}")
        if not os.path.isdir(destination_dir):
            raise NotADirectoryError(f"Path is not a directory: {destination}")

        target_path = self.resolve_upload_target_path(destination_dir, filename)
        if os.path.exists(target_path) and not overwrite:
            raise FileExistsError(f"Destination exists: {target_path}")

        try:
            parent_dir = os.path.dirname(target_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(target_path, "wb") as output:
                uploaded_bytes = 0
                while True:
                    if cancel_callback and cancel_callback():
                        raise UploadCancelledError(f"Upload cancelled: {filename}")

                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    output.write(chunk)
                    uploaded_bytes += len(chunk)
                    if progress_callback:
                        progress_callback(uploaded_bytes)

                if progress_callback and size == 0:
                    progress_callback(0)
        except Exception:
            if os.path.exists(target_path):
                os.remove(target_path)
            raise

        return self.get_file_entry(target_path)

    def delete_path(self, path: str, recursive: bool = False):
        abs_path = self._resolve_path(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Path not found: {path}")

        if os.path.isdir(abs_path):
            if recursive:
                shutil.rmtree(abs_path)
            else:
                try:
                    os.rmdir(abs_path)
                except OSError:
                    raise OSError("Directory not empty")
        else:
            os.remove(abs_path)

    def rename_path(
        self, source: str, destination: str, overwrite: bool = False
    ) -> str:
        abs_source = self._resolve_path(source)
        abs_dest = self._resolve_path(destination)

        if not os.path.exists(abs_source):
            raise FileNotFoundError(f"Source not found: {source}")

        if os.path.exists(abs_dest):
            if not overwrite:
                raise FileExistsError(f"Destination exists: {destination}")
            # If overwrite is true, os.rename usually overwrites on Linux for files,
            # but for directories it might fail or behave differently depending on emptiness.
            # shutil.move is safer generally but might not be atomic.

        shutil.move(abs_source, abs_dest)
        return abs_dest

    def get_usb_devices(self) -> List[USBDevice]:
        devices = []
        try:
            # Use lsblk to get JSON output
            result = subprocess.run(
                [
                    "lsblk",
                    "-J",
                    "-o",
                    "NAME,MOUNTPOINT,SIZE,FSTYPE,LABEL,VENDOR,MODEL,SERIAL,RM,RO,TYPE,UUID",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)

            for device in data.get("blockdevices", []):
                self._process_lsblk_device(device, devices)

        except Exception as e:
            logger.error(f"Error listing USB devices: {e}")
            # Fallback could be checking /media or /run/media

        return devices

    def _process_lsblk_device(self, device_info: dict, devices_list: List[USBDevice]):
        # Check if it's removable (RM="1" or True) and has a mountpoint
        # Note: lsblk JSON output types can vary slightly by version.

        is_removable = (
            str(device_info.get("rm", "0")) == "1" or device_info.get("rm") is True
        )
        mount_point = device_info.get("mountpoint")

        # We generally want children partitions if available
        children = device_info.get("children", [])
        if children:
            for child in children:
                self._process_lsblk_device(child, devices_list)
            return

        # If it's a leaf node (partition or disk with no partitions)
        if is_removable and mount_point:
            # Calculate usage if mounted
            used = 0
            free = 0
            total = 0
            usage_pct = 0.0

            try:
                usage = shutil.disk_usage(mount_point)
                total = usage.total
                used = usage.used
                free = usage.free
                if total > 0:
                    usage_pct = (used / total) * 100
            except OSError:
                pass

            devices_list.append(
                USBDevice(
                    device=f"/dev/{device_info.get('name')}",
                    mount_point=mount_point,
                    label=device_info.get("label"),
                    filesystem=device_info.get("fstype"),
                    total_size=total,
                    total_size_human=self._human_readable_size(total),
                    used_size=used,
                    used_size_human=self._human_readable_size(used),
                    free_size=free,
                    free_size_human=self._human_readable_size(free),
                    usage_percent=round(usage_pct, 1),
                    is_removable=True,
                    vendor=device_info.get("vendor"),
                    model=device_info.get("model"),
                    serial=device_info.get("serial"),
                )
            )
