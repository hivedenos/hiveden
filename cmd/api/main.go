package main

import (
	"log"

	"github.com/hiveden/hiveden/internal/api"
	"github.com/hiveden/hiveden/internal/docker"

	"github.com/gin-gonic/gin"
	"github.com/spf13/viper"
)

func main() {
	viper.SetDefault("network_name", docker.DefaultNetworkName)
	v,_ := docker.NewDockerManager(viper.GetString("network_name"))
	dm := v

	apiHandler := api.NewAPIHandler(dm)

	r := gin.Default()

	dockerGroup := r.Group("/docker")

	containersGroup := dockerGroup.Group("/containers")
	{
		containersGroup.GET("", apiHandler.ListContainers)
		containersGroup.POST("", apiHandler.CreateContainer)
		containersGroup.POST("/:id/start", apiHandler.StartContainer)
		containersGroup.POST("/:id/stop", apiHandler.StopContainer)
		containersGroup.DELETE("/:id", apiHandler.RemoveContainer)
	}

	networksGroup := dockerGroup.Group("/networks")
	{
		networksGroup.GET("", apiHandler.ListNetworks)
		networksGroup.POST("", apiHandler.CreateNetwork)
		networksGroup.DELETE("/:id", apiHandler.RemoveNetwork)
	}

	if err := r.Run(":8080"); err != nil {
		log.Fatalf("failed to run server: %v", err)
	}
}
