package docker

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/client"
	"gopkg.in/yaml.v2"
)

const (
	DefaultNetworkName = "hiveden-network"
)

// DockerManager provides methods to interact with the Docker API.
type DockerManager struct {
	cli         *client.Client
	networkName string
}

// NewDockerManager creates a new DockerManager instance.
func NewDockerManager(networkName string) (*DockerManager, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, err
	}

	if networkName == "" {
		networkName = DefaultNetworkName
	}

	return &DockerManager{cli: cli, networkName: networkName}, nil
}

// ListContainers lists containers. The 'all' parameter determines whether to list all containers or only running ones.
func (dm *DockerManager) ListContainers(ctx context.Context, all bool) ([]ContainerInfo, error) {
	containers, err := dm.cli.ContainerList(ctx, container.ListOptions{All: all})
	if err != nil {
		return nil, err
	}

	var containerInfos []ContainerInfo
	for _, c := range containers {
		managedBy, ok := c.Labels["managed-by"]
		if !ok {
			managedBy = "unknown"
		}

		var name string
		if len(c.Names) > 0 {
			name = strings.TrimPrefix(c.Names[0], "/")
		}

		info := ContainerInfo{
			ID:        c.ID[:12],
			Image:     c.Image,
			ImageID:   c.ImageID,
			Name:      name,
			Uptime:    formatUptime(c.Created),
			ManagedBy: managedBy,
		}
		containerInfos = append(containerInfos, info)
	}

	return containerInfos, nil
}

func formatUptime(createdAt int64) string {
	if createdAt == 0 {
		return "N/A"
	}
	uptime := time.Since(time.Unix(createdAt, 0))
	days := int(uptime.Hours() / 24)
	hours := int(uptime.Hours()) % 24
	minutes := int(uptime.Minutes()) % 60

	if days > 0 {
		return fmt.Sprintf("%d days", days)
	}
	if hours > 0 {
		return fmt.Sprintf("%d hours", hours)
	}
	if minutes > 0 {
		return fmt.Sprintf("%d minutes", minutes)
	}
	return "Less than a minute"
}

// CreateContainer creates a new container and attaches it to the hiveden network.
func (dm *DockerManager) CreateContainer(ctx context.Context, imageName string, containerName string) (container.CreateResponse, error) {
	networkExists, err := dm.NetworkExists(ctx, dm.networkName)
	if err != nil {
		return container.CreateResponse{}, fmt.Errorf("failed to check if network exists: %w", err)
	}

	if !networkExists {
		return container.CreateResponse{}, fmt.Errorf("network %s does not exist", dm.networkName)
	}

	return dm.cli.ContainerCreate(ctx, &container.Config{
		Image: imageName,
		Labels: map[string]string{
			"managed-by": "hiveden",
		},
	}, &container.HostConfig{},
		&network.NetworkingConfig{
			EndpointsConfig: map[string]*network.EndpointSettings{
				dm.networkName: {},
			},
		}, nil, containerName)
}

// StartContainer starts a container.
func (dm *DockerManager) StartContainer(ctx context.Context, containerID string) error {
	return dm.cli.ContainerStart(ctx, containerID, container.StartOptions{})
}

// StopContainer stops a container.
func (dm *DockerManager) StopContainer(ctx context.Context, containerID string) error {
	return dm.cli.ContainerStop(ctx, containerID, container.StopOptions{})
}

// RemoveContainer removes a container.
func (dm *DockerManager) RemoveContainer(ctx context.Context, containerID string) error {
	return dm.cli.ContainerRemove(ctx, containerID, container.RemoveOptions{})
}

// ExportManagedContainers exports all containers managed by hiveden to a YAML file.
func (dm *DockerManager) ExportManagedContainers(ctx context.Context, filePath string) error {
	containers, err := dm.ListContainers(ctx, true)
	if err != nil {
		return err
	}

	var managedContainers []ContainerConfig
	for _, c := range containers {
		if c.ManagedBy == "hiveden" {
			managedContainers = append(managedContainers, ContainerConfig{
				Name:  c.Name,
				Image: c.Image,
			})
		}
	}

	config := struct {
		Containers []ContainerConfig `yaml:"containers"`
	}{
		Containers: managedContainers,
	}

	data, err := yaml.Marshal(&config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	return os.WriteFile(filePath, data, 0644)
}
