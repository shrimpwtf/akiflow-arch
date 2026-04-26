# akiflow-bin

Unofficial Arch Linux package for [Akiflow](https://akiflow.com) — extracts the Windows installer and runs it via system Electron. Includes a KDE Plasma panel widget for upcoming tasks.

## Installation

```bash
yay -S akiflow-bin
```

## KDE Plasma Widget

The package installs a Plasma panel widget that shows your upcoming Akiflow tasks. Add it by right-clicking your panel → Add Widgets → search for "Akiflow".

The widget reads a status file written by the app, so Akiflow needs to be running for it to display tasks.

## Auto-updates

A GitHub Actions workflow runs daily, checks `download.akiflow.com/builds/latest.yml` for new releases, and automatically updates the PKGBUILD and pushes to AUR. No manual maintenance required.

## Notes

- Requires `electron` from the Arch repos
- This is an unofficial port — not affiliated with Akiflow
- The app is extracted from the Windows NSIS installer and patched to enable the Plasma widget integration
