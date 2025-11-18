package main

import (
	"fmt"
	"log"
	"os"

	"github.com/hiveden/hiveden/internal/docker"
	"gopkg.in/yaml.v2"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var dockerManager *docker.DockerManager

func main() {
	rootCmd := &cobra.Command{
		Use: "hiveden",
		PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
			var err error
			dockerManager, err = docker.NewDockerManager(viper.GetString("network_name"))
			if err != nil {
				return fmt.Errorf("failed to create Docker manager: %v", err)
			}
			return nil
		},
	}

	rootCmd.PersistentFlags().String("network-name", "hiveden-network", "Name for the Docker network")
	viper.BindPFlag("network_name", rootCmd.PersistentFlags().Lookup("network-name"))
	viper.SetDefault("network_name", docker.DefaultNetworkName)

	var configFile string
	rootCmd.PersistentFlags().StringVar(&configFile, "config", "cmd/cli/config.yaml", "config file (default is cmd/cli/config.yaml)")

	containersCmd := &cobra.Command{
		Use:   "containers",
		Short: "Manage containers",
	}

	containersCmd.AddCommand(buildListCommand())
	containersCmd.AddCommand(buildCreateCommand())
	containersCmd.AddCommand(buildStartCommand())
	containersCmd.AddCommand(buildStopCommand())
	containersCmd.AddCommand(buildRemoveCommand())
	containersCmd.AddCommand(buildRunAllCommand(&configFile))

	rootCmd.AddCommand(containersCmd)

	containersCmd.AddCommand(buildExportCommand())

	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func buildListCommand() *cobra.Command {
	var all bool

	cmd := &cobra.Command{
		Use:   "list",
		Short: "List all containers",
		RunE: func(cmd *cobra.Command, args []string) error {
			containers, err := dockerManager.ListContainers(cmd.Context(), all)
			if err != nil {
				return err
			}

			for _, container := range containers {
				fmt.Printf("ID: %s, Name: %s, Image: %s, ImageID: %s, Uptime: %s, ManagedBy: %s\n", container.ID, container.Name, container.Image, container.ImageID, container.Uptime, container.ManagedBy)
			}

			return nil
		},
	}

	cmd.Flags().BoolVar(&all, "all", false, "Show all containers (default shows just running)")

	return cmd
}

func buildCreateCommand() *cobra.Command {
	var imageName, containerName string

	cmd := &cobra.Command{
		Use:   "create",
		Short: "Create a new container",
		RunE: func(cmd *cobra.Command, args []string) error {
			resp, err := dockerManager.CreateContainer(cmd.Context(), imageName, containerName)
			if err != nil {
				return err
			}

			fmt.Printf("Container created with ID: %s\n", resp.ID)
			return nil
		},
	}

	cmd.Flags().StringVar(&imageName, "image", "", "Image name for the container")
	cmd.Flags().StringVar(&containerName, "name", "", "Name for the container")
	cmd.MarkFlagRequired("image")

	return cmd
}

func buildStartCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "start [containerID]",
		Short: "Start a container",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return dockerManager.StartContainer(cmd.Context(), args[0])
		},
	}
}

func buildStopCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "stop [containerID]",
		Short: "Stop a container",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return dockerManager.StopContainer(cmd.Context(), args[0])
		},
	}
}

func buildRemoveCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "remove [containerID]",
		Short: "Remove a container",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return dockerManager.RemoveContainer(cmd.Context(), args[0])
		},
	}
}

type ContainerConfig struct {
	Name  string `yaml:"name"`
	Image string `yaml:"image"`
}

type Config struct {
	Containers []ContainerConfig `yaml:"containers"`
}

func buildRunAllCommand(configFile *string) *cobra.Command {
	return &cobra.Command{
		Use:   "run-all",
		Short: "Create and start all containers from a config file",
		RunE: func(cmd *cobra.Command, args []string) error {
			data, err := os.ReadFile(*configFile)
			if err != nil {
				return fmt.Errorf("failed to read config file: %w", err)
			}

			var config Config
			if err := yaml.Unmarshal(data, &config); err != nil {
				return fmt.Errorf("failed to unmarshal config: %w", err)
			}

			for _, containerConfig := range config.Containers {
				fmt.Printf("Creating container %s with image %s...\n", containerConfig.Name, containerConfig.Image)
				resp, err := dockerManager.CreateContainer(cmd.Context(), containerConfig.Image, containerConfig.Name)
				if err != nil {
					log.Printf("Failed to create container %s: %v", containerConfig.Name, err)
					continue
				}

				fmt.Printf("Starting container %s (%s)...\n", containerConfig.Name, resp.ID[:12])
				if err := dockerManager.StartContainer(cmd.Context(), resp.ID); err != nil {
					log.Printf("Failed to start container %s: %v", containerConfig.Name, err)
				}
			}

			return nil
		},
	}
}

func buildExportCommand() *cobra.Command {
	var filePath string

	cmd := &cobra.Command{
		Use:   "export",
		Short: "Export all hiveden-managed containers to a config file",
		RunE: func(cmd *cobra.Command, args []string) error {
			if filePath == "" {
				return fmt.Errorf("file path must be specified with --file")
			}
			return dockerManager.ExportManagedContainers(cmd.Context(), filePath)
		},
	}

	cmd.Flags().StringVar(&filePath, "file", "", "File path to export the configuration to")

	return cmd
}
