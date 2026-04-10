# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-04-10

### Changed

- **RET**: Departures are read from RET halt pages on ret.nl (HTML) instead of OVapi; **stop ID** must be the URL slug (e.g. `beurs`, `centraal-station`). Numeric `NL:Q:` codes are no longer used for RET.
- Added dependency on `beautifulsoup4` for RET parsing.

### Migration

- Re-add or edit each RET config entry with the slug from `https://www.ret.nl/home/reizen/halte/<slug>.html`.

## [1.1.0] - 2024-11-16

### Added

- Optional NS **Disruptions** binary sensor when “Monitor disruptions” is enabled in integration options.
- `api_disruptions.py`, `binary_sensor.py`, and coordinator support for disruption payloads.

## [1.0.0] - 2024-11-16

### Added
- Initial release of RET & NS Departures integration
- Support for RET (Rotterdam) metro, tram, and bus departures (initially via OVapi; see 2.0.0)
- Support for NS (Nederlandse Spoorwegen) train departures via official NS API
- UI-based configuration flow for easy setup
- Two sensor types per stop/station:
  - Next departure sensor with full departure information
  - Time to next departure sensor (in minutes)
- Rich sensor attributes including:
  - Line/train numbers
  - Destinations
  - Platform information
  - Delay information
  - Scheduled vs actual times
  - List of upcoming departures
- Line filtering for RET departures
- Options flow for updating configuration
- Async/await implementation for non-blocking operation
- Timezone-aware datetime handling (Europe/Amsterdam)
- DataUpdateCoordinator for efficient data polling
- English and Dutch translations
- Comprehensive unit tests
- Detailed documentation and examples

### Features
- Default polling interval: 30 seconds
- Minimum polling interval: 15 seconds
- Default max departures: 5
- Automatic retry on network errors
- Proper error handling and logging
- Cancellation detection for NS trains
- Device grouping for multiple sensors

[2.0.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v2.0.0
[1.1.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v1.1.0
[1.0.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v1.0.0
