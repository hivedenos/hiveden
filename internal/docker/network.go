package docker

import (
	"context"

	"github.com/docker/docker/api/types/network"
)

// CreateNetwork creates a new network.
func (dm *DockerManager) CreateNetwork(ctx context.Context, networkName string) (network.CreateResponse, error) {
	return dm.cli.NetworkCreate(ctx, networkName, network.CreateOptions{})
}

// RemoveNetwork removes a network.
func (dm *DockerManager) RemoveNetwork(ctx context.Context, networkID string) error {
	return dm.cli.NetworkRemove(ctx, networkID)
}

// ListNetworks lists all networks.
func (dm *DockerManager) ListNetworks(ctx context.Context) ([]NetworkInfo, error) {
	networks, err := dm.cli.NetworkList(ctx, network.ListOptions{})
	if err != nil {
		return nil, err
	}

	var networkInfos []NetworkInfo
	for _, n := range networks {
		networkInfos = append(networkInfos, NetworkInfo{
			ID:   n.ID,
			Name: n.Name,
		})
	}

	return networkInfos, nil
}

// NetworkExists checks if a network exists.
func (dm *DockerManager) NetworkExists(ctx context.Context, networkName string) (bool, error) {
	networks, err := dm.cli.NetworkList(ctx, network.ListOptions{})
	if err != nil {
		return false, err
	}

	for _, n := range networks {
		if n.Name == networkName {
			return true, nil
		}
	}

	return false, nil
}
