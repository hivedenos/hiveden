Name:           hiveden
Version:        0.1.0
Release:        1%{?dist}
Summary:        A CLI tool and REST API for managing your personal server.

License:        MIT
URL:            https://github.com/hiveden/hiveden
Source0:        https://github.com/hiveden/hiveden/archive/v%{version}.tar.gz
Source1:        hiveden.service

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-build
Requires:       systemd

%description
A CLI tool and REST API for managing your personal server.

%pre
getent group hiveden >/dev/null || groupadd -r hiveden
getent passwd hiveden >/dev/null || \
    useradd -r -g hiveden -d /opt/hiveden -s /sbin/nologin \
    -c "Hiveden user" hiveden
exit 0

%prep
%setup -q -n hiveden-%{version}

%build
%py3_build

%install
%py3_install
install -D -m644 %{SOURCE1} %{buildroot}%{_unitdir}/hiveden.service

%post
%systemd_post hiveden.service

%preun
%systemd_preun hiveden.service

%postun
%systemd_postun_with_restart hiveden.service

%files
%license LICENSE
%{_bindir}/hiveden
%{python3_sitelib}/hiveden
%{python3_sitelib}/hiveden-*.dist-info
%{_unitdir}/hiveden.service
