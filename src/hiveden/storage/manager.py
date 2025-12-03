from typing import List
from hiveden.storage.devices import get_system_disks, get_unused_disks
from hiveden.storage.strategies import generate_strategies
from hiveden.storage.models import Disk, StorageStrategy

class StorageManager:
    def list_disks(self) -> List[Disk]:
        return get_system_disks()

    def get_strategies(self) -> List[StorageStrategy]:
        unused = get_unused_disks()
        return generate_strategies(unused)

    # Future implementation for applying strategies
    def apply_strategy(self, strategy_name: str):
        raise NotImplementedError("Strategy application not yet implemented")
