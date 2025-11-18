package arch

import (
	"github.com/Jguer/go-alpm/v2"
)

func getAllInstalledPackages(handle *alpm.Handle) []alpm.IPackage {
	allPackages := []alpm.IPackage{}
	localDB, err := handle.LocalDB()
	if err != nil {
		return allPackages
	}

	for _, p := range localDB.PkgCache().Slice() {
		allPackages = append(allPackages, p)
	}

	return allPackages
}
