from hiveden.hwosinfo.os import get_os_info

try:
    import libzfs
except ImportError:
    os_info = get_os_info()
    distro = os_info.get("id").lower()
    if distro in ["arch"]:
        raise ImportError("py-libzfs is not installed. Please install it with: pacman -S python-pylibzfs")
    elif distro in ["debian", "ubuntu"]:
        raise ImportError("py-libzfs is not installed. Please install it with: apt-get install py-libzfs")
    else:
        raise ImportError("py-libzfs is not installed. Please install it using your system package manager.")


class ZFSManager:
    def __init__(self):
        self.zfs = libzfs.ZFS()

    def list_pools(self):
        return [p.name for p in self.zfs.pools]

    def create_pool(self, name, devices):
        self.zfs.create(name, devices, fstype='zfs')

    def destroy_pool(self, name):
        pool = self.zfs.get(name)
        self.zfs.destroy(pool.name)

    def list_datasets(self, pool_name):
        pool = self.zfs.get(pool_name)
        return [d.name for d in pool.root_dataset.children]

    def create_dataset(self, name):
        self.zfs.create(name)

    def destroy_dataset(self, name):
        dataset = self.zfs.get_dataset(name)
        dataset.delete()
