Name:           hiveden
Version:        0.1.0
Release:        1%{?dist}
Summary:        A CLI tool and REST API for managing your personal server.

License:        MIT
URL:            https://github.com/hiveden/hiveden
Source0:        https://github.com/hiveden/hiveden/archive/v%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-build

%description
A CLI tool and REST API for managing your personal server.

%prep
%setup -q -n hiveden-%{version}

%build
%py3_build

%install
%py3_install

%files
%license LICENSE
%{_bindir}/hiveden
%{python3_sitelib}/hiveden
%{python3_sitelib}/hiveden-*.dist-info
