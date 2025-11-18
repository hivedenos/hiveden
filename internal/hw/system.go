package hw

import (
	"fmt"

	"github.com/shirou/gopsutil/v3/host"
)

// GetSystemInfo retrieves and returns key information about the host system.
func GetSystemInfo() (*SystemInfo, error) {
	info, err := host.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get host info: %w", err)
	}

	sysInfo := &SystemInfo{
		OS:            info.OS,
		Distro:        info.Platform,
		Version:       info.PlatformVersion,
		KernelVersion: info.KernelVersion,
		Architecture:  info.KernelArch,
	}

	return sysInfo, nil
}
