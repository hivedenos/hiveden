package arch

import (
	"errors"
	"fmt"
	"os"

	"github.com/Jguer/go-alpm/v2"
)

const (
	dbPath  = "/var/lib/pacman"
	root    = "/"
	logFile = "/dev/stdout" // For logging pacman actions
)

// Arch represents an Arch Linux package manager instance.
type Arch struct {
	handle *alpm.Handle
}

// New creates a new instance of the Arch package manager.
func New() (*Arch, error) {
	h, err := alpm.Initialize(root, dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize alpm: %w", err)
	}

	for _, dbName := range []string{"core", "extra", "community", "multilib"} {
		if _, err := h.RegisterSyncDB(dbName, alpm.SigUseDefault); err != nil {
			fmt.Fprintf(os.Stderr, "warning: could not register sync db '%s'\n", dbName)
		}
	}

	return &Arch{handle: h}, nil
}

// Close releases the alpm handle.
func (a *Arch) Close() {
	if a.handle != nil {
		a.handle.Release()
	}
}

// Install installs or upgrades one or more packages, following the logic from the official examples.
func (a *Arch) Install(packages ...string) error {
	localDB, err := a.handle.LocalDB()
	if err != nil {
		return fmt.Errorf("could not get local db: %w", err)
	}
	syncDBs, err := a.handle.SyncDBs()
	if err != nil {
		return fmt.Errorf("could not get sync dbs: %w", err)
	}

	var toInstall []alpm.IPackage

	for _, name := range packages {
		// 1. Search for the package in the remote repos.
		for _, syncDB := range syncDBs.Slice() {
			pkgs := syncDB.Search([]string{name})
			if len(pkgs.Slice()) == 0 {
				return fmt.Errorf("package '%s' not found in remote repositories", name)
			}
			remotePkg := pkgs.Slice()[0] // Use the first search result.

			// 2. Check if the package is already installed.
			localPkg := localDB.Pkg(remotePkg.Name())
			if localPkg != nil {
				// 3. If installed, compare versions and add to list if remote is newer.
				cmp := alpm.VerCmp(remotePkg.Version(), localPkg.Version())
				if cmp > 0 {
					fmt.Printf("Queueing upgrade for %s (%s -> %s)\n", remotePkg.Name(), localPkg.Version(), remotePkg.Version())
					toInstall = append(toInstall, remotePkg)
				} else {
					fmt.Printf("%s is already up to date (version %s)\n", localPkg.Name(), localPkg.Version())
				}
			} else {
				// 4. If not installed, add it to the list.
				fmt.Printf("Queueing new installation for %s %s\n", remotePkg.Name(), remotePkg.Version())
				toInstall = append(toInstall, remotePkg)
			}
		}
	}

	if len(toInstall) == 0 {
		fmt.Println("No new packages to install or upgrade.")
		return nil
	}

	// 5. Perform a single transaction with all collected packages.
	if err := a.handle.TransInit(alpm.TransFlagNoDeps); err != nil {
		return fmt.Errorf("failed to initialize transaction: %w", err)
	}
	defer a.handle.TransRelease()

	for _, pkg := range toInstall {
		if err := a.handle.AddPkg(pkg); err != nil {
			return fmt.Errorf("failed to add package %s to transaction: %w", pkg.Name(), err)
		}
	}

	if err := a.handle.TransPrepare(); err != nil {
		return fmt.Errorf("failed to prepare transaction: %w", err)
	}
	if err := a.handle.TransCommit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	fmt.Println("Installation/upgrade complete.")
	return nil
}

// Remove removes one or more installed packages.
func (a *Arch) Remove(packages ...string) error {
	return errors.New("Not implemented yet")
}

// Update synchronizes remote databases and upgrades all outdated packages (equivalent to `pacman -Syu`).
func (a *Arch) Update() error {
	allInstalledPkgs := getAllInstalledPackages(a.handle)
	dbs, err := a.handle.SyncDBs()
	if err != nil {
		return fmt.Errorf("failed to get sync dbs: %w", err)
	}

	for _, db := range dbs.Slice() {
		db.SetUsage(alpm.UsageUpgrade)
	}

	for _, pkg := range allInstalledPkgs {
		pkg.SyncNewVersion(dbs)
	}

	return nil
}

// ListInstalled lists all installed packages.
func (a *Arch) ListInstalled() ([]*Package, error) {
	packages := []*Package{}
	allPackages := getAllInstalledPackages(a.handle)

	for _, p := range allPackages {
		packages = append(packages, newPackage(p))
	}
	return packages, nil
}

// Search searches for packages in the sync databases.
func (a *Arch) Search(packagesToSearch ...string) ([]*Package, error) {
	var packages []*Package
	dbs, err := a.handle.SyncDBs()
	if err != nil {
		return nil, fmt.Errorf("failed to get sync dbs: %w", err)
	}

	for _, db := range dbs.Slice() {
		foundPackages := db.Search(packagesToSearch)

		for _, pkg := range foundPackages.Slice() {
			packages = append(packages, newPackage(pkg))
		}
	}

	return packages, nil
}

// findInstalledPackages is a helper to find packages in the local database.
func (a *Arch) findInstalledPackages(names ...string) ([]alpm.IPackage, error) {
	localDB, err := a.handle.LocalDB()
	if err != nil {
		return nil, fmt.Errorf("failed to get local db: %w", err)
	}

	var pkgs []alpm.IPackage
	for _, name := range names {
		pkg := localDB.Pkg(name)
		if pkg == nil {
			return nil, fmt.Errorf("installed package not found: %s", name)
		}
		pkgs = append(pkgs, pkg)
	}
	return pkgs, nil
}
