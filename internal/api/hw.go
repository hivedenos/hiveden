package api

import (
	"net/http"

	"github.com/hiveden/hiveden/internal/hw"

	"github.com/gin-gonic/gin"
)

// GetHardwareInfo handles the GET /hw endpoint.
func (h *APIHandler) GetHardwareInfo(c *gin.Context) {
	hwInfo, err := hw.GetHardwareInfo()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, hwInfo)
}
