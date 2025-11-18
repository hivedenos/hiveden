package arch

import "github.com/Jguer/go-alpm/v2"

// Package represents an Arch Linux package.
type Package struct {
	Name        string
	Version     string
	Description string
	URL         string
	Size        int64
}

func newPackage(p alpm.IPackage) *Package {
	return &Package{
		Name:        p.Name(),
		Version:     p.Version(),
		Description: p.Description(),
		URL:         p.URL(),
		Size:        p.Size(),
	}
}
