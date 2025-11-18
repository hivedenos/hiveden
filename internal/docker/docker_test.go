package docker

import (
	"context"
	"errors"
	"io"
	"testing"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/network"
	v1 "github.com/opencontainers/image-spec/specs-go/v1"
)

type mockClient struct {
	createContainerErr   bool
	startContainerErr    bool
	stopContainerErr     bool
	removeContainerErr   bool
	listContainersErr    bool
	createNetworkErr     bool
	removeNetworkErr     bool
	listNetworksErr      bool
	lastCreateConfig     *container.Config
	lastNetworkingConfig *network.NetworkingConfig
	ContainerListFunc    func(ctx context.Context, options container.ListOptions) ([]container.Summary, error)
}

func (m *mockClient) ContainerCreate(ctx context.Context, config *container.Config, hostConfig *container.HostConfig, networkingConfig *network.NetworkingConfig, platform *v1.Platform, containerName string) (container.CreateResponse, error) {
	if m.createContainerErr {
		return container.CreateResponse{}, errors.New("failed to create container")
	}
	m.lastCreateConfig = config
	m.lastNetworkingConfig = networkingConfig
	return container.CreateResponse{ID: "12345"}, nil
}

func (m *mockClient) ContainerStart(ctx context.Context, containerID string, options container.StartOptions) error {
	if m.startContainerErr {
		return errors.New("failed to start container")
	}
	return nil
}

func (m *mockClient) ContainerStop(ctx context.Context, containerID string, options container.StopOptions) error {
	if m.stopContainerErr {
		return errors.New("failed to stop container")
	}
	return nil
}

func (m *mockClient) ContainerRemove(ctx context.Context, containerID string, options container.RemoveOptions) error {
	if m.removeContainerErr {
		return errors.New("failed to remove container")
	}
	return nil
}

func (m *mockClient) ContainerList(ctx context.Context, options container.ListOptions) ([]container.Summary, error) {
	if m.ContainerListFunc != nil {
		return m.ContainerListFunc(ctx, options)
	}
	if m.listContainersErr {
		return nil, errors.New("failed to list containers")
	}
	return []container.Summary{
		{ID: "1234567890ab", Names: []string{"/test-container"}},
	}, nil
}

func (m *mockClient) NetworkCreate(ctx context.Context, name string, options network.CreateOptions) (network.CreateResponse, error) {
	if m.createNetworkErr {
		return network.CreateResponse{}, errors.New("failed to create network")
	}
	return network.CreateResponse{ID: "net-12345"}, nil
}

func (m *mockClient) NetworkRemove(ctx context.Context, networkID string) error {
	if m.removeNetworkErr {
		return errors.New("failed to remove network")
	}
	return nil
}

func (m *mockClient) NetworkList(ctx context.Context, options network.ListOptions) ([]network.Summary, error) {
	if m.listNetworksErr {
		return nil, errors.New("failed to list networks")
	}
	return []network.Summary{
		{ID: "net-12345", Name: "test-network"},
	}, nil
}

func (m *mockClient) ImagePull(ctx context.Context, ref string, options image.PullOptions) (io.ReadCloser, error) {
	return nil, nil
}

func TestNewDockerManager(t *testing.T) {
	dm, err := NewDockerManager("test-network")
	if err != nil {
		t.Fatalf("NewDockerManager() error = %v", err)
	}
	if dm.cli == nil {
		t.Fatal("expected cli to be initialized")
	}
	if dm.networkName != "test-network" {
		t.Fatalf("expected networkName to be 'test-network', got '%s'", dm.networkName)
	}
}

func TestCreateContainer(t *testing.T) {
	mock := &mockClient{}
	dm := &DockerManager{cli: mock, networkName: "test-network"}
	_, err := dm.CreateContainer(context.Background(), "test-image", "test-container")
	if err != nil {
		t.Fatalf("CreateContainer() error = %v", err)
	}

	if managedBy, ok := mock.lastCreateConfig.Labels["managed-by"]; !ok || managedBy != "hiveden" {
		t.Errorf("expected managed-by label to be 'hiveden', got '%s'", managedBy)
	}
	if _, ok := mock.lastNetworkingConfig.EndpointsConfig["test-network"]; !ok {
		t.Errorf("expected container to be attached to 'test-network'")
	}
}

func TestCreateContainerError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{createContainerErr: true}}
	_, err := dm.CreateContainer(context.Background(), "test-image", "test-container")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestStartContainer(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	err := dm.StartContainer(context.Background(), "12345")
	if err != nil {
		t.Fatalf("StartContainer() error = %v", err)
	}
}

func TestStartContainerError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{startContainerErr: true}}
	err := dm.StartContainer(context.Background(), "12345")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestStopContainer(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	err := dm.StopContainer(context.Background(), "12345")
	if err != nil {
		t.Fatalf("StopContainer() error = %v", err)
	}
}

func TestStopContainerError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{stopContainerErr: true}}
	err := dm.StopContainer(context.Background(), "12345")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestRemoveContainer(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	err := dm.RemoveContainer(context.Background(), "12345")
	if err != nil {
		t.Fatalf("RemoveContainer() error = %v", err)
	}
}

func TestRemoveContainerError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{removeContainerErr: true}}
	err := dm.RemoveContainer(context.Background(), "12345")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestListContainers(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	containers, err := dm.ListContainers(context.Background(), true)
	if err != nil {
		t.Fatalf("ListContainers() error = %v", err)
	}
	if len(containers) != 1 {
		t.Fatalf("expected 1 container, got %d", len(containers))
	}
}

func TestListContainersWithLabel(t *testing.T) {
	mock := &mockClient{}
	dm := &DockerManager{cli: mock}

	// Mock a container with the managed-by label
	mockContainer := container.Summary{
		ID:      "1234567890ab",
		Names:   []string{"/test-container"},
		Image:   "test-image",
		ImageID: "img-123",
		Labels:  map[string]string{"managed-by": "hiveden"},
	}
	mock.ContainerListFunc = func(ctx context.Context, options container.ListOptions) ([]container.Summary, error) {
		return []container.Summary{mockContainer}, nil
	}

	containers, err := dm.ListContainers(context.Background(), true)
	if err != nil {
		t.Fatalf("ListContainers() error = %v", err)
	}

	if len(containers) != 1 {
		t.Fatalf("expected 1 container, got %d", len(containers))
	}

	if containers[0].ManagedBy != "hiveden" {
		t.Errorf("expected managed-by to be 'hiveden', got '%s'", containers[0].ManagedBy)
	}
}

func TestListContainersError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{listContainersErr: true}}
	_, err := dm.ListContainers(context.Background(), true)
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestCreateNetwork(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	_, err := dm.CreateNetwork(context.Background(), "test-network")
	if err != nil {
		t.Fatalf("CreateNetwork() error = %v", err)
	}
}

func TestCreateNetworkError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{createNetworkErr: true}}
	_, err := dm.CreateNetwork(context.Background(), "test-network")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestRemoveNetwork(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	err := dm.RemoveNetwork(context.Background(), "net-12345")
	if err != nil {
		t.Fatalf("RemoveNetwork() error = %v", err)
	}
}

func TestRemoveNetworkError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{removeNetworkErr: true}}
	err := dm.RemoveNetwork(context.Background(), "net-12345")
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}

func TestListNetworks(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{}}
	networks, err := dm.ListNetworks(context.Background())
	if err != nil {
		t.Fatalf("ListNetworks() error = %v", err)
	}
	if len(networks) != 1 {
		t.Fatalf("expected 1 network, got %d", len(networks))
	}
}

func TestListNetworksError(t *testing.T) {
	dm := &DockerManager{cli: &mockClient{listNetworksErr: true}}
	_, err := dm.ListNetworks(context.Background())
	if err == nil {
		t.Fatal("expected an error, but got none")
	}
}
