package hw

import "github.com/jaypipes/ghw"

// HardwareInfo contains information about the system's hardware.
type HardwareInfo struct {
	CPU         *ghw.CPUInfo    `json:"cpu"`
	Memory      *ghw.MemoryInfo `json:"memory"`
	BlockStorage *ghw.BlockInfo  `json:"block_storage"`
}
