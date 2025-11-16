# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-11-16

### Added
- Initial release of RET & NS Departures integration
- Support for RET (Rotterdam) metro, tram, and bus departures via OVapi
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

[1.0.0]: https://github.com/yourusername/ret-ns-departures/releases/tag/v1.0.0
