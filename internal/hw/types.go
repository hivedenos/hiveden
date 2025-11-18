package hw

import "github.com/jaypipes/ghw"

// HardwareInfo contains information about the system's hardware.
type HardwareInfo struct {
	CPU          *ghw.CPUInfo    `json:"cpu"`
	Memory       *ghw.MemoryInfo `json:"memory"`
	BlockStorage *ghw.BlockInfo  `json:"block_storage"`
}

// SystemInfo holds details about the host system.
type SystemInfo struct {
	OS            string `json:"os"`
	Distro        string `json:"distro"`
	Version       string `json:"version"`
	KernelVersion string `json:"kernelVersion"`
	Architecture  string `json:"architecture"`
}
