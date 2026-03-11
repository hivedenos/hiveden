# Python Dependency Strategy

## Problem

Hiveden supports two installation paths:

1. **Direct Python installs** via `pip`
2. **System packages** via `apt`, `dnf`, or `pacman`

Those paths use different dependency sources:

- **Core runtime Python deps** should come from the Python metadata for `pip`
- **System packages** should map those deps to distro package names wherever possible
- **PyPI-only deps** should remain in `pip` post-install hooks only when the distro does not provide them

The old packaging mixed both approaches and reinstalled distro-managed dependencies with `pip` during package installation.

## Solution

We now split dependency ownership clearly:

1. **`pyproject.toml` declares the pip/runtime dependency set** for direct Python installs
2. **Distro packaging maps those dependencies to system package names** where available
3. **Post-install pip hooks are reserved for PyPI-only gaps** on a given distro

## Implementation

### pyproject.toml

```toml
[project]
dependencies = [
    "click",
    "fastapi",
    "uvicorn",
    "docker",
    "PyYAML",
    "psutil",
    "lxc",
    "paramiko",
    "websockets",
    "psycopg2",
    "APScheduler",
    "python-multipart",
    "yoyo-migrations",
]

[project.optional-dependencies]
# Optional integrations
pihole = [
    "pihole6api",
]
```

### Arch Linux (hiveden.install)

```bash
post_install() {
    # Install only packages not covered by repo packages
    pip install --no-warn-script-location APScheduler pihole6api yoyo-migrations 2>/dev/null || true
}

post_upgrade() {
    post_install
}
```

### Debian/Ubuntu (postinst)

```bash
#!/bin/bash

mkdir -p /opt/hiveden
chown -R hiveden:hiveden /opt/hiveden
chmod 750 /opt/hiveden

# Python dependencies are provided by Debian package dependencies.
```

### Fedora/RHEL (spec file)

```spec
%post
%systemd_post hiveden.service
# Install only PyPI-only gaps for Fedora.
pip3 install --no-warn-script-location pihole6api yoyo-migrations 2>/dev/null || true
```

## Why This Works

1. **Pip installs are accurate**: Python metadata reflects the real runtime requirements
2. **System packages stay clean**: distro-managed dependencies are not reinstalled with `pip`
3. **PyPI-only gaps stay explicit**: post-install hooks only cover packages missing from distro repos
4. **Maintenance is clearer**: package metadata and distro packaging each own their side of the split

## Flags Used

- `--no-warn-script-location`: Suppress warnings about script locations
- `2>/dev/null || true`: Suppress errors and don't fail package installation if pip has issues

## Current Split

- **Declared in `pyproject.toml`**: core runtime Python packages used by direct `pip` installs
- **Optional pip extra**: `pihole6api` via the `pihole` extra
- **Installed by Debian packages**: all current runtime deps via `Depends`
- **Installed by Fedora post-install**: `pihole6api`, `yoyo-migrations`
- **Installed by Arch post-install**: `APScheduler`, `pihole6api`, `yoyo-migrations`

## Notes

- Distro availability changes over time, so Fedora and Arch may eventually move more packages out of the pip fallback path.
- If a dependency becomes optional in the application code, it should move to a feature-specific extra in `pyproject.toml`.
