class ZFSManager:
    def __init__(self):
        try:
            import libzfs
            self.zfs = libzfs.ZFS()
        except Exception:
            self.zfs = None

    def list_pools(self):
        if self.zfs is None:
            return []
        return [p.name for p in self.zfs.pools]

    def create_pool(self, name, devices):
        if self.zfs is None:
            return
        self.zfs.create(name, devices, fstype='zfs')

    def destroy_pool(self, name):
        if self.zfs is None:
            return
        pool = self.zfs.get(name)
        self.zfs.destroy(pool.name)

    def list_datasets(self, pool_name):
        if self.zfs is None:
            return []
        pool = self.zfs.get(pool_name)
        return [d.name for d in pool.root_dataset.children]

    def create_dataset(self, name):
        if self.zfs is None:
            return
        self.zfs.create(name)

    def destroy_dataset(self, name):
        if self.zfs is None:
            return
        dataset = self.zfs.get_dataset(name)
        dataset.delete()

    def get_all_devices(self):
        """Return a list of all devices used by ZFS pools."""
        if self.zfs is None:
            return []
        used_devices = []
        for pool in self.zfs.pools:
            for vdev in pool.vdev_tree.children:
                if vdev.is_leaf:
                    used_devices.append(vdev.path)
        return used_devices
