Name:           hiveden
Version:        0.0.0
Release:        1%{?dist}
Summary:        A CLI tool and REST API for managing your personal server.

License:        MIT
URL:            https://github.com/hiveden/hiveden
Source0:        https://github.com/hiveden/hiveden/archive/v%{version}.tar.gz
Source1:        hiveden.service
Source2:        hiveden.default.yaml

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-build
Requires:       systemd
Requires:       python3-psycopg2
Requires:       lshw

%description
A CLI tool and REST API for managing your personal server.

%pre
getent group hiveden >/dev/null || groupadd -r hiveden
getent passwd hiveden >/dev/null || \
    useradd -r -g hiveden -d /opt/hiveden -s /sbin/nologin \
    -c "Hiveden user" hiveden

# Clean up old artifacts
if [ -d "%{python3_sitelib}/hiveden" ]; then
    find %{python3_sitelib}/hiveden -name "*.pyc" -delete
    find %{python3_sitelib}/hiveden -name "__pycache__" -type d -empty -delete
fi
exit 0

%prep
%setup -q -n hiveden-%{version}

%build
%py3_build

%install
%py3_install
install -D -m644 %{SOURCE1} %{buildroot}%{_unitdir}/hiveden.service
install -D -m644 %{SOURCE2} %{buildroot}%{_sysconfdir}/hiveden/config.yaml
mkdir -p %{buildroot}/opt/hiveden

%post
%systemd_post hiveden.service
# Install all Python dependencies via pip
pip3 install --no-warn-script-location click fastapi uvicorn docker PyYAML psutil lxc paramiko websockets pihole6api yoyo-migrations python-multipart 2>/dev/null || true

%preun
%systemd_preun hiveden.service

%postun
%systemd_postun_with_restart hiveden.service

%files
%license LICENSE
%{_bindir}/hiveden
%{python3_sitelib}/hiveden
%{python3_sitelib}/hiveden-*.*-info
%{_unitdir}/hiveden.service
%config(noreplace) %{_sysconfdir}/hiveden/config.yaml
%dir /opt/hiveden
