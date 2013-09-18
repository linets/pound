%define version 2.6
%define rpmrelease 4
# betarelease is either 0 or something like b1
%define betarelease 0

%define distname Pound
%define name pound
# Do we have filesystem >= 2.3.2 (new pki location) ?
%define use_etc_pki %(eval [ $(rpm -q --queryformat '%{VERSION}' filesystem \| %{__sed} -e "s/\\.//g") -ge 232 ] && echo 1 || echo 0 )
%if %{use_etc_pki}
%define certs_dir %{_sysconfdir}/pki/tls/certs
%define pki_dir %{_sysconfdir}/pki/%{name}
%else
%define certs_dir %{_datadir}/ssl/certs
%define pki_dir %{_datadir}/ssl/certs
%endif
%define ssl_pem_file %{pki_dir}/%{name}.pem

Summary: %{name} is a reverse proxy, load balancer and HTTPS front-end for Web servers
Name: %{name}
Version: %{version}
%if %{betarelease}
Release: 0.%{betarelease}_%{rpmrelease}%{?dist}
%else
Release: %{rpmrelease}%{?dist}
%endif
License: GPLv3
Group: System Environment/Daemons
URL: http://www.apsis.ch/%{name}/
Packager: Simon Matter <simon.matter@invoca.ch>
Vendor: Invoca Systems
Distribution: Invoca Linux Server
%if %{betarelease}
Source0: http://www.apsis.ch/%{name}/%{distname}-%{version}%{betarelease}.tgz
%else
Source0: http://www.apsis.ch/%{name}/%{distname}-%{version}.tgz
%endif
Source1: %{name}.cfg
Source2: %{name}.init
Patch0: pound-2.5-remove-owner.patch
Patch1: pound-2.6-gcc.patch
Patch2: pound-2.6-reneg-ciphers-altnames-nosslv2.patch
# Patches >=100 will/should be fixed in SCM
BuildRoot: %{_tmppath}/%{name}-%{version}-root
Requires(pre): %{_sbindir}/groupadd, %{_sbindir}/useradd
Requires(post): /sbin/chkconfig, openssl
Requires(preun): /sbin/chkconfig, /sbin/service
Requires(postun): /sbin/service
BuildRequires: openssl-devel, pkgconfig, pcre-devel, sed, perl

%description
The %{name} program is a reverse proxy, load balancer and HTTPS
front-end for Web server(s). %{name} was developped to enable
distributing the load among several Web-servers and to allow for a
convenient SSL wrapper for those Web servers that do not offer it
natively. %{name} is distributed under the GPL - no warranty, it's free
to use, copy and give away.

%prep
%if %{betarelease}
%setup -q -n %{distname}-%{version}%{betarelease}
%else
%setup -q -n %{distname}-%{version}
%endif
%patch0 -p1 -b .remove-owner
%patch1 -p1 -b .oldgcc
%patch2 -p1 -b .re-ci-alt-no


%build
if pkg-config openssl; then
  CPPFLAGS="$(pkg-config --cflags-only-I openssl) $CPPFLAGS"; export CPPFLAGS
  CFLAGS="$(pkg-config --cflags openssl) $CFLAGS"; export CFLAGS
  LDFLAGS="$(pkg-config --libs-only-L openssl) $LDFLAGS"; export LDFLAGS
fi
if pcre-config --version; then
  CPPFLAGS="$(pcre-config --cflags-posix) $CPPFLAGS"; export CPPFLAGS
  CFLAGS="$(pcre-config --cflags-posix) $CFLAGS"; export CFLAGS
  LDFLAGS="$(pcre-config --libs-posix) $LDFLAGS"; export LDFLAGS
fi
%{configure} \
  --sysconfdir=%{_sysconfdir}/%{name} \
  --disable-tcmalloc \
  --disable-hoard \
  --with-ssl=/usr/local/ssl
%{__make}

%install
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot}
 
%{__install} -d %{buildroot}%{_initrddir}
%{__install} -d %{buildroot}%{_sysconfdir}/%{name}
%{__install} -d %{buildroot}%{_var}/empty/%{name}/%{_sysconfdir}
%{__install} -d %{buildroot}%{_var}/empty/%{name}/%{_lib}
%{__install} -d %{buildroot}%{pki_dir}
%{__install} -d %{buildroot}%{_var}/run/%{name}

touch %{buildroot}%{_var}/empty/%{name}/%{_sysconfdir}/localtime
%{__install} -p -m 0644 %{SOURCE1} %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg
%{__sed} -e "s/@@LIB@@/%{_lib}/g" %{SOURCE2} > %{buildroot}%{_initrddir}/%{name}

%{__make} install DESTDIR=%{buildroot} INSTALL="install -p"

# create the ghost pem file
touch %{buildroot}%{ssl_pem_file}
%if %{use_etc_pki}
# change config file so ssl certificates are under /etc rather than /usr/share
# preserve timestamp of the files
%{__cp} -a %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
%{__perl} -pi -e \
's@/usr/share/ssl/certs/%{name}.pem@%{ssl_pem_file}@g; \
 s@/usr/share/ssl/certs/ca-bundle.crt@/etc/pki/tls/certs/ca-bundle.crt@' \
 %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
%{__perl} -pi -e \
's@/usr/share/ssl/certs/@%{certs_dir}/@g' \
 %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
touch -r %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
%{__mv} -f %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg.pki.$$ %{buildroot}%{_sysconfdir}/%{name}/%{name}.cfg
%endif

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot}

%pre
getent group %{name} > /dev/null || %{_sbindir}/groupadd -r %{name} 2> /dev/null || :
getent passwd %{name} > /dev/null || \
  %{_sbindir}/useradd -g %{name} -s /sbin/nologin -r -c "Pound User" -d %{_var}/empty/%{name} %{name} 2> /dev/null || :

# Let postun know whether the service was running
if [ -e /var/lock/subsys/%{name} ]; then
  /sbin/service %{name} stop >/dev/null 2>&1 || :
  touch /var/lock/subsys/%{name}
fi

%post
/sbin/chkconfig --add %{name}

# Create SSL certificates
exec > /dev/null 2> /dev/null
%if %{use_etc_pki}
# if the certificate is only in the old location, move it to the new location
if [ -f %{_datadir}/ssl/certs/%{name}.pem -a ! -f %{ssl_pem_file} ]; then
%{__mv} %{_datadir}/ssl/certs/%{name}.pem %{ssl_pem_file}
fi
%endif
if [ ! -f %{ssl_pem_file} ]; then
pushd %{certs_dir}
umask 077
%{__cat} << EOF | %{__make} %{name}.pem
--
SomeState
SomeCity
SomeOrganization
SomeOrganizationalUnit
localhost.localdomain
root@localhost.localdomain
EOF
%{__chown} root.%{name} %{name}.pem
%{__chmod} 640 %{name}.pem
%if %{use_etc_pki}
%{__mv} %{name}.pem %{ssl_pem_file}
%endif
popd
fi

%if %{use_etc_pki}
# change existing config so ssl certificates are under /etc rather than /usr/share
# preserve timestamp of the files
if %{__grep} -q "/usr/share/ssl/certs/" %{_sysconfdir}/%{name}/%{name}.cfg; then
  %{__cp} -a %{_sysconfdir}/%{name}/%{name}.cfg %{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
  %{__perl} -pi -e \
  's@/usr/share/ssl/certs/%{name}.pem@%{ssl_pem_file}@g; \
   s@/usr/share/ssl/certs/ca-bundle.crt@/etc/pki/tls/certs/ca-bundle.crt@' \
   %{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
  %{__perl} -pi -e \
  's@/usr/share/ssl/certs/@%{certs_dir}/@g' \
   %{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
  touch -r %{_sysconfdir}/%{name}/%{name}.cfg %{_sysconfdir}/%{name}/%{name}.cfg.pki.$$
  %{__mv} -f %{_sysconfdir}/%{name}/%{name}.cfg.pki.$$ %{_sysconfdir}/%{name}/%{name}.cfg
fi
%endif

%preun
if [ $1 = 0 ]; then
  /sbin/service %{name} stop >/dev/null 2>&1 || :
  /sbin/chkconfig --del %{name}
  %{__rm} -f %{_var}/run/%{name}/*
fi

%postun
if [ $1 != 0 ]; then
  /sbin/service %{name} condrestart >/dev/null 2>&1 || :
fi

%files
%defattr(-,root,root)
%doc CHANGELOG FAQ README
%attr(0755,root,root) %{_sbindir}/%{name}*
%dir %{_sysconfdir}/%{name}
%attr(0644,root,root) %config(noreplace) %{_sysconfdir}/%{name}/%{name}.cfg
%attr(0755,root,root) %config %{_initrddir}/%{name}
%{_mandir}/man?/%{name}*.*
%dir %attr(0711,root,root) %{_var}/empty/%{name}
%dir %{_var}/empty/%{name}/%{_sysconfdir}
%dir %{_var}/empty/%{name}/%{_lib}
%ghost %verify(not md5 size mtime) %{_var}/empty/%{name}/%{_sysconfdir}/localtime
%{_var}/run/%{name}
%if %{use_etc_pki}
%dir %{pki_dir}
%endif
%attr(0640,root,%{name}) %ghost %config(missingok,noreplace) %verify(not md5 size mtime) %{ssl_pem_file}

%changelog
* Fri Nov 30 2012 Fabian Arias <farias@linets.cl> 2.6-3
- add altnames patch
- add nosslv2 patch
- add cipher renegotiation patch

* Thu Nov 29 2012 Fabian Arias <farias@linets.cl> 2.6-2
- add altnames patch

* Fri Dec 30 2011 Simon Matter <simon.matter@invoca.ch> 2.6-1
- update to release 2.6

* Tue Aug 02 2011 Simon Matter <simon.matter@invoca.ch> 2.5-6
- run ad user pound
- change chroot jail to /var/empty/pound

* Mon Aug 01 2011 Simon Matter <simon.matter@invoca.ch> 2.5-5
- setup chroot directory in init script

* Mon Aug 01 2011 Simon Matter <simon.matter@invoca.ch> 2.5-4
- build with standard malloc, no google-perftools or hoard

* Thu Jun 16 2011 Simon Matter <simon.matter@invoca.ch> 2.5-3
- add memory_leak patch

* Fri Apr 15 2011 Simon Matter <simon.matter@invoca.ch> 2.5-2
- mass rebuild

* Tue Feb 02 2010 Simon Matter <simon.matter@invoca.ch> 2.5-1
- update to release 2.5

* Thu Dec 17 2009 Simon Matter <simon.matter@invoca.ch> 2.4.5-2
- add fix to make configure detect GNU libc compatible malloc

* Mon Jun 29 2009 Simon Matter <simon.matter@invoca.ch> 2.4.5-1
- update to release 2.4.5

* Wed Jan 14 2009 Simon Matter <simon.matter@invoca.ch> 2.4.4-1
- update to release 2.4.4

* Tue Sep 30 2008 Simon Matter <simon.matter@invoca.ch> 2.4.3-2
- preserve config file timestamp while upgrading pki location

* Sat May 31 2008 Simon Matter <simon.matter@invoca.ch> 2.4.3-1
- update to release 2.4.3

* Thu Apr 24 2008 Simon Matter <simon.matter@invoca.ch> 2.4.2-1
- update to release 2.4.2

* Mon Apr 07 2008 Simon Matter <simon.matter@invoca.ch> 2.4.1-1
- update to release 2.4.1

* Fri Mar 28 2008 Simon Matter <simon.matter@invoca.ch> 2.4-3
- disable real-time scheduling, patch by Samuel Graenacher

* Fri Feb 29 2008 Simon Matter <simon.matter@invoca.ch> 2.4-2
- don't report duplicate syslog messages, use correct local time

* Mon Feb 11 2008 Simon Matter <simon.matter@invoca.ch> 2.4-1
- update to release 2.4

* Tue Aug 28 2007 Simon Matter <simon.matter@invoca.ch> 2.3.2-2
- fix handling of certificates on new distributions

* Fri May 18 2007 Simon Matter <simon.matter@invoca.ch> 2.3.2-1
- update to release 2.3.2

* Tue May 01 2007 Simon Matter <simon.matter@invoca.ch> 2.3.1-1
- update to release 2.3.1

* Tue Apr 17 2007 Simon Matter <simon.matter@invoca.ch> 2.3-2
- modify init script to not add /lib/libgcc* to chroot jail on startup

* Wed Apr 11 2007 Simon Matter <simon.matter@invoca.ch> 2.3-1
- update to release 2.3

* Thu Apr 05 2007 Simon Matter <simon.matter@invoca.ch> 2.2.8-1
- update to release 2.2.8

* Mon Mar 12 2007 Simon Matter <simon.matter@invoca.ch> 2.2.7-1
- update to release 2.2.7

* Tue Mar 06 2007 Simon Matter <simon.matter@invoca.ch> 2.2.6-2
- build with TCMalloc from google-perftools

* Fri Mar 02 2007 Simon Matter <simon.matter@invoca.ch> 2.2.6-1
- update to release 2.2.6

* Tue Feb 20 2007 Simon Matter <simon.matter@invoca.ch> 2.2.5-1
- update to release 2.2.5

* Sat Feb 10 2007 Simon Matter <simon.matter@invoca.ch> 2.2.4-1
- update to release 2.2.4

* Tue Jan 23 2007 Simon Matter <simon.matter@invoca.ch> 2.2.3-2
- replace logging patch

* Sat Jan 20 2007 Simon Matter <simon.matter@invoca.ch> 2.2.3-1
- update to release 2.2.3

* Tue Jan 16 2007 Simon Matter <simon.matter@invoca.ch> 2.2.2-1
- update to release 2.2.2

* Wed Jan 03 2007 Simon Matter <simon.matter@invoca.ch> 2.2.1-1
- update to release 2.2.1

* Tue Jan 02 2007 Simon Matter <simon.matter@invoca.ch> 2.2-2
- add sprintf_overrun patch

* Sat Dec 16 2006 Simon Matter <simon.matter@invoca.ch> 2.2-1
- update to release 2.2

* Sat Dec 09 2006 Simon Matter <simon.matter@invoca.ch> 2.1.8-1
- update to release 2.1.8

* Thu Dec 07 2006 Simon Matter <simon.matter@invoca.ch> 2.1.7-1
- update to release 2.1.7
- add pound-2.1.7-make patch

* Sun Nov 19 2006 Simon Matter <simon.matter@invoca.ch> 2.1.6-2
- add bottleneck patch

* Sat Nov 04 2006 Simon Matter <simon.matter@invoca.ch> 2.1.6-1
- update to release 2.1.6

* Thu Nov 02 2006 Simon Matter <simon.matter@invoca.ch> 2.1.5-2
- add emergency_back-end patch

* Mon Oct 23 2006 Simon Matter <simon.matter@invoca.ch> 2.1.5-1
- update to release 2.1.5

* Sat Oct 14 2006 Simon Matter <simon.matter@invoca.ch> 2.1.4-1
- update to release 2.1.4

* Tue Sep 26 2006 Simon Matter <simon.matter@invoca.ch> 2.1.3-3
- add no_cont patch

* Fri Sep 22 2006 Simon Matter <simon.matter@invoca.ch> 2.1.3-2
- small spec file changes

* Thu Sep 21 2006 Simon Matter <simon.matter@invoca.ch> 2.1.3-1
- update to release 2.1.3

* Tue Sep 19 2006 Simon Matter <simon.matter@invoca.ch> 2.1.2-1
- update to release 2.1.2
- remove msdav build option

* Mon Sep 11 2006 Simon Matter <simon.matter@invoca.ch> 2.1.1-1
- update to release 2.1.1

* Wed Aug 30 2006 Simon Matter <simon.matter@invoca.ch> 2.1-2
- add loglevel2 patch

* Mon Aug 07 2006 Simon Matter <simon.matter@invoca.ch> 2.1-1
- update to release 2.1

* Fri Jun 23 2006 Simon Matter <simon.matter@invoca.ch> 2.0.9-1
- update to release 2.0.9

* Tue Jun 20 2006 Simon Matter <simon.matter@invoca.ch> 2.0.8-1
- update to release 2.0.8

* Mon Jun 06 2006 Simon Matter <simon.matter@invoca.ch> 2.0.7-1
- update to release 2.0.7

* Mon May 22 2006 Simon Matter <simon.matter@invoca.ch> 2.0.6-1
- update to release 2.0.6

* Mon May 15 2006 Simon Matter <simon.matter@invoca.ch> 2.0.5-1
- update to release 2.0.5

* Fri May 05 2006 Simon Matter <simon.matter@invoca.ch> 2.0.4-4
- remove /dev bind mount from the init script

* Thu May 04 2006 Simon Matter <simon.matter@invoca.ch> 2.0.4-3
- modify init script to add /lib/libgcc* to chroot jail on startup

* Mon Mar 20 2006 Simon Matter <simon.matter@invoca.ch> 2.0.4-1
- update to release 2.0.4
- build using posixpcre

* Tue Feb 21 2006 Simon Matter <simon.matter@invoca.ch> 2.0.2-1
- update to release 2.0.2

* Mon Feb 06 2006 Simon Matter <simon.matter@invoca.ch> 2.0.1-1
- update to release 2.0.1

* Wed Feb 01 2006 Simon Matter <simon.matter@invoca.ch> 2.0-1
- update to release 2.0

* Wed Jan 04 2006 Simon Matter <simon.matter@invoca.ch> 2.0-0.b6_1
- update to release 2.0b6

* Sat Dec 24 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b5_1
- update to release 2.0b5

* Fri Dec 16 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b4_4
- replace timeout patch, add fixed svc.c

* Tue Dec 13 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b4_2
- add haportaddr patch
- add timeout patch

* Wed Dec 07 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b4_1
- update to release 2.0b4
- add patch to make check-only mode work with 2.x code

* Fri Nov 18 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b3_1
- update to release 2.0b3

* Wed Nov 09 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b2_1
- update to release 2.0b2
- remove HTTPS config patch

* Tue Nov 01 2005 Simon Matter <simon.matter@invoca.ch> 2.0-0.b1_1
- update to release 2.0b1

* Mon Oct 24 2005 Simon Matter <simon.matter@invoca.ch> 1.9.4-1
- update to release 1.9.4

* Wed Sep 28 2005 Simon Matter <simon.matter@invoca.ch> 1.9.3-1
- update to release 1.9.3

* Mon Sep 26 2005 Simon Matter <simon.matter@invoca.ch> 1.9.2-1
- update to release 1.9.2

* Tue Aug 30 2005 Simon Matter <simon.matter@invoca.ch> 1.9.1-3
- fix new pkg-config stuff

* Mon Aug 29 2005 Simon Matter <simon.matter@invoca.ch> 1.9.1-2
- make build work on systems without pkg-config

* Mon Aug 29 2005 Simon Matter <simon.matter@invoca.ch> 1.9.1-1
- update to release 1.9.1
- pull in CPPFLAGS and LDFLAGS from openssl's pkg-config data, if it exists

* Mon Aug 22 2005 Simon Matter <simon.matter@invoca.ch> 1.9-3
- cosmetic changes in pre and post scripts

* Fri Aug 19 2005 Simon Matter <simon.matter@invoca.ch> 1.9-2
- fix ssl pki stuff to handle new locations

* Thu Jun 02 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.9

* Thu May 19 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8.5

* Mon May 09 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8.4

* Tue Apr 26 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8.3

* Tue Mar 08 2005 Simon Matter <simon.matter@invoca.ch>
- updated to second release of 1.8.2

* Mon Mar 07 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8.2

* Sat Feb 12 2005 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8.1

* Tue Dec 14 2004 Simon Matter <simon.matter@invoca.ch>
- added buildreq for openssl-devel

* Mon Nov 08 2004 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.8

* Tue Mar 30 2004 Simon Matter <simon.matter@invoca.ch>
- added poll patch

* Wed Mar 24 2004 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.7

* Tue Mar 23 2004 Simon Matter <simon.matter@invoca.ch>
- updated to -current release

* Mon Jan 19 2004 Simon Matter <simon.matter@invoca.ch>
- updated to -current release

* Fri Nov 07 2003 Simon Matter <simon.matter@invoca.ch>
- added FAQ

* Tue Oct 21 2003 Simon Matter <simon.matter@invoca.ch>
- chroot jail uses bind mount to get access to /dev/*

* Thu Oct 16 2003 Simon Matter <simon.matter@invoca.ch>
- binaries go to /usr/sbin/

* Tue Oct 14 2003 Simon Matter <simon.matter@invoca.ch>
- updated to release 1.5

* Fri Oct 03 2003 Simon Matter <simon.matter@invoca.ch>
- updated snapshot release

* Fri Sep 26 2003 Simon Matter <simon.matter@invoca.ch>
- updated snapshot release

* Tue Sep 24 2003 Simon Matter <simon.matter@invoca.ch>
- updated snapshot release

* Thu Sep 11 2003 Simon Matter <simon.matter@invoca.ch>
- updated snapshot release

* Wed Aug 13 2003 Simon Matter <simon.matter@invoca.ch>
- added new configure options

* Thu Jul 03 2003 Simon Matter <simon.matter@invoca.ch>
- small config fixes

* Mon May 12 2003 Simon Matter <simon.matter@invoca.ch>
- disable msdav support by default

* Tue Apr 29 2003 Simon Matter <simon.matter@invoca.ch>
- fixed RootJail configuration

* Sun Apr 27 2003 Simon Matter <simon.matter@invoca.ch>
- enable msdav support

* Sat Apr 26 2003 Simon Matter <simon.matter@invoca.ch>
- initial build
