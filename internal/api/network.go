package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// ListNetworks handles the GET /networks endpoint.
func (h *APIHandler) ListNetworks(c *gin.Context) {
	networks, err := h.dm.ListNetworks(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, networks)
}

// CreateNetwork handles the POST /networks endpoint.
func (h *APIHandler) CreateNetwork(c *gin.Context) {
	var reqBody struct {
		Name string `json:"name"`
	}

	if err := c.ShouldBindJSON(&reqBody); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	resp, err := h.dm.CreateNetwork(c.Request.Context(), reqBody.Name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, resp)
}

// RemoveNetwork handles the DELETE /networks/{id} endpoint.
func (h *APIHandler) RemoveNetwork(c *gin.Context) {
	networkID := c.Param("id")

	if err := h.dm.RemoveNetwork(c.Request.Context(), networkID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}
