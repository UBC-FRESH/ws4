# Prometheus under Wine: negative result

Date: 2026-11-09
Parent: #923 P157
Related: #944 P157.9, #945 P157.10
Status: Prometheus installs under Wine; the application does not start

## Summary

Prometheus 2023.06.01 was downloaded from the free EOL distribution and installed in a
clean 64-bit Wine prefix. The installer completed and registered the COM components, but
`Prometheus.exe` exits at startup with a native CLR exception and never opens a window.

This is a Wine/runtime blocker, not a missing-download or licence issue. Prometheus remains
a Windows-host task unless a different Wine/runtime combination is found.

## Environment

- Host: Ubuntu 24.04, x86-64.
- Wine: `wine-11.0`.
- Prefix: clean 64-bit `WINEPREFIX`, Windows 10 mode.
- Installer: `Prometheus_2023.06.01_EOL.exe`.
- Application: `C:\Program Files\Prometheus\Prometheus.exe`, PE32+ .NET/Mono assembly.

## Prerequisites installed

- Visual C++ 2015–2022 x64 redistributable (`vc_redist.x64.exe`).
- .NET Framework 4.8 (`winetricks dotnet48`).
- Java 8 JRE (Temurin 8u512) at `C:\Java\jre`.
- `JAVA_HOME=C:\Java` in the Wine environment.

The installer was then run silently in the same prefix. It completed and registered:

```text
C:\Program Files\Prometheus\FWICom.dll
C:\Program Files\Prometheus\FuelCom.dll
C:\Program Files\Prometheus\GridCom.dll
C:\Program Files\Prometheus\WeatherCom.dll
C:\Program Files\Prometheus\FireEngine.dll
C:\Program Files\Prometheus\PrometheusCom.dll
```

## Failure

Launching the installed application:

```text
Unhandled Exception: System.Runtime.InteropServices.SEHException:
External component has thrown an exception.
   at WinMainCRTStartup()
```

No window is created. The same failure occurs after:

- setting Windows 10 compatibility mode,
- forcing native `mscoree`,
- adding Java 8 JRE,
- installing .NET 4.8,
- installing the VC++ runtime,
- using a clean 64-bit prefix.

Before .NET/VC++ were installed, the failure was different: Wine reported missing
`mfc140.dll` / `MFCM140.dll` and exited with status `c0000135`. Those were fixed, but the
CLR/native startup exception remains.

## Tried

- NSIS extraction of the installer, then running the extracted `Prometheus.exe`.
- Full installer after prerequisites were present.
- 32-bit and 64-bit Wine prefixes.
- Wine Mono and native .NET Framework 4.8.
- Native Java 8 JRE and `JAVA_HOME` registration.
- Windows 10 mode.
- `WINEDLLOVERRIDES=mscoree=n`.

## Conclusion

Do not treat Prometheus as available in this container. For an accepted-model comparison:

1. Run Prometheus on a Windows host, or
2. Use **BurnP3+FireSTARR**, which is the Linux-compatible CFS reference path, or
3. Use the direct FireSTARR comparison already recorded in
   `notes/reports/p157-firestarr-comparison.md`.

The FireSTARR side-by-side is the current external-model evidence. Prometheus Scenario 2b
remains the missing apples-to-apples reference.
