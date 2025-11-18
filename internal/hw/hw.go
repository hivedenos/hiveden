package hw

import (
	"fmt"

	"github.com/jaypipes/ghw"
)


// GetHardwareInfo returns a struct containing information about the system's hardware.
func GetHardwareInfo() (*HardwareInfo, error) {
	cpu, err := ghw.CPU()
	if err != nil {
		return nil, fmt.Errorf("failed to get CPU info: %w", err)
	}

	memory, err := ghw.Memory()
	if err != nil {
		return nil, fmt.Errorf("failed to get memory info: %w", err)
	}

	block, err := ghw.Block()
	if err != nil {
		return nil, fmt.Errorf("failed to get block storage info: %w", err)
	}

	return &HardwareInfo{
		CPU:         cpu,
		Memory:      memory,
		BlockStorage: block,
	}, nil
}
