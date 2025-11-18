package docker

import (
	"context"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/network"
	v1 "github.com/opencontainers/image-spec/specs-go/v1"
)

// ContainerInfo holds custom information about a container.
type ContainerInfo struct {
	ID        string
	Image     string
	ImageID   string
	Name      string
	Uptime    string
	ManagedBy string
}

// NetworkInfo holds custom information about a network.
type NetworkInfo struct {
	ID   string
	Name string
}

// Client is an interface for the Docker client.
type Client interface {
	ContainerCreate(ctx context.Context, config *container.Config, hostConfig *container.HostConfig, networkingConfig *network.NetworkingConfig, platform *v1.Platform, containerName string) (container.CreateResponse, error)
	ContainerStart(ctx context.Context, containerID string, options container.StartOptions) error
	ContainerStop(ctx context.Context, containerID string, options container.StopOptions) error
	ContainerRemove(ctx context.Context, containerID string, options container.RemoveOptions) error
	ContainerList(ctx context.Context, options container.ListOptions) ([]container.Summary, error)
	NetworkCreate(ctx context.Context, name string, options network.CreateOptions) (network.CreateResponse, error)
	NetworkRemove(ctx context.Context, networkID string) error
	NetworkList(ctx context.Context, options network.ListOptions) ([]network.Summary, error)
}

// ContainerConfig represents a container in the YAML config file.
type ContainerConfig struct {
	Name  string `yaml:"name"`
	Image string `yaml:"image"`
}

// NetworkConfig represents a network in the YAML config file.
type NetworkConfig struct {
	Name string `yaml:"name"`
}
