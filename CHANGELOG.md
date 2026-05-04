# Changelog

## [1.0.1] - 2026-05-04

### Added
- **Auto-start service commands**: `install-service`, `uninstall-service`, `service-status`
  - Automatically start best config on Windows login
  - Uses registry (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)

- **Tie-breaker sorting**: When score is equal, config with lower ping wins
  - Updated `list` command shows Ping column for detailed comparison

- **Custom sites file support**: `--sites-file` parameter for `optimize` command
  - Create your own list of sites to test
  - Example file: `sites_example.txt`

### Changed
- Enhanced `list` command output with detailed statistics
- Improved target loading priority system

## [1.0.0] - 2026-05-03

### Added
- Initial release
- 3-cycle optimization (test → mutate → combine)
- WARP config generation for AmneziaVPN
- Telegram proxy integration (tg-ws-proxy)
- Dependency management
