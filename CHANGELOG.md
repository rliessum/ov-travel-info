# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.5.3] - 2026-08-18

### Added

- **RET empty boards show why.** When a halt has no departures, the next-departure sensor name becomes **No service — …** (Dutch: **Geen dienst**) and **What's wrong** explains the matching [omleiding / dienstregeling](https://www.ret.nl/home/reizen/omleidingen-verstoringen.html) notice — for example Hofplein works cancelling Schiekade on [tram 8](https://www.ret.nl/home/reizen/dienstregeling/tram-8.html), with replacement stops and a timetable link. A Disruptions binary sensor is now created for RET stops as well.

## [3.5.2] - 2026-08-18

### Fixed

- **RET**: Halt pages that RET marks out of service (notably the documented `centraal-station` slug) no longer come back empty. The client follows the live replacement (`rotterdam-centraal`) and, if needed, RET's own halte search. Existing entries keep working without reconfiguration.
- **RET**: Setup help text and examples now use slugs that still have a departure board (`beurs`, `rotterdam-centraal`). Check [Dienstregeling](https://www.ret.nl/) when a halt is empty — several inner-city tram stops (including Schiekade) have no service during the Hofplein works through 22 November 2026.

## [3.5.1] - 2026-08-18

### Changed

- **Disruptions more-info is readable.** The binary sensor name becomes the main disruption (and `+N` when there are more). Opening it shows **What's wrong** first — route, cause, situation, extra travel time, duration, and affected stations — instead of only a nested list. The next-departure sensor also leads with that message when a disruption is active.

## [3.5.0] - 2026-08-18

### Added

- **Spoorkaart getStoring** map data for NS disruptions via [getStoring](https://apiportal.ns.nl/api-details#api=spoorkaart-api&operation=getStoring). When disruption monitoring is on, each disruption is enriched with a map centroid, bounding box, station codes, and level from the rail-map GeoJSON. The Disruptions binary sensor exposes `latitude` / `longitude` and a Point `geojson` FeatureCollection for map cards.

## [3.4.0] - 2026-08-18

### Added

- **Virtual Train image for the next NS departure** via [getImage](https://apiportal.ns.nl/api-details#api=virtual-train-API&operation=getImage). A **Next train** image entity is added for NS stations, and the next-departure sensor uses the picture when a public URL is returned.

## [3.3.0] - 2026-08-18

### Added

- **NS Disruptions API v3** (`getDisruptions_v3`) is used for station disruption monitoring. New NS stations enable monitoring by default (toggle on the station picker, or later in options). The next-departure sensor lists active disruption titles. If the dedicated Disruptions API is not in the subscription, the Reisinformatie disruptions endpoint is used as a fallback.

## [3.2.0] - 2026-08-18

### Added

- **Next departure sensor shows the train and destination** in its name (for example `IC 2834 to Amsterdam Centraal`) while the state stays the departure time. The same text is on both departure sensors as the `description` attribute.

## [3.1.2] - 2026-08-18

### Added

- **NS setup reuses an existing API key.** When you add another NS station, the key from a previous NS entry is used if you leave the field empty. You can still type a different key.

## [3.1.1] - 2026-08-18

### Added

- HACS / Home Assistant brand icon: the public-domain [OV-chipkaart mark](https://commons.wikimedia.org/wiki/File:OV-chipkaart_logo.svg) in `custom_components/ret_ns_departures/brand/` (and repo-root `brand/`).

## [3.1.0] - 2026-08-18

### Added

- **NS setup looks up station code and official name** from the [NS App Stations API](https://apiportal.ns.nl/api-details#api=nsapp-stations-api&operation=getNearestStations). After the API key, pick a nearby station from your Home Assistant home location (or a pin on the map), or search by name/code. The selected station’s code and name are filled in from the API.
- If the Stations API is not in the subscription, setup falls back to the Reisinformatie station list.

## [3.0.0] - 2026-08-17

### Breaking

- **Next Departure sensor is now a `timestamp` device-class sensor.** The state is a datetime instead of an ISO string, and the `Cancelled` state is gone: cancelled departures are skipped and the state points to the next departure that will actually run (or `unknown` if none). Dashboards render it as relative time ("in 8 minutes"). Update templates that compared the state to `'Cancelled'` — use the `cancelled` flag inside the `departures` attribute instead.
- **Time to Next Departure sensor** now has `device_class: duration` and also skips cancelled departures, so both sensors always describe the same departure.
- Top-level attributes on both sensors now describe the departure shown in the state (the next non-cancelled one) rather than blindly the first item in the feed. The `departures` attribute still lists everything, including cancelled services.
- Minimum Home Assistant version is now **2024.11.0** (`hacs.json`).

### Changed

- Entity names come from translation keys (`Next departure`, `Time to next departure`, `Disruptions`; Dutch: `Volgende vertrek`, `Tijd tot volgende vertrek`, `Storingen`). Existing entity IDs are preserved via the entity registry.
- Coordinator is stored on `entry.runtime_data` instead of `hass.data`, takes the config entry directly, and registers itself with the entry (modern HA pattern).
- Disruption sensor icons moved to `icons.json` with state-based icons.
- CI now tests Python 3.12/3.13 (matching Home Assistant's supported versions).

## [2.1.0] - 2026-08-17

### Fixed

- **RET**: A departure whose scheduled time had just passed (a delayed or just-missed service) was moved to tomorrow; scheduled times now only roll over to the next day when they are more than 6 hours in the past.
- **RET**: Delay is now computed directly from actual vs scheduled time, fixing wrong values around midnight.
- Options flow no longer assigns `config_entry` manually (removed in Home Assistant 2025.12); options can be edited again on current HA versions.
- Config entry reload now uses `hass.config_entries.async_reload` instead of a manual unload/setup cycle.
- Coordinator `last_update` is a real UTC timestamp instead of a monotonic clock value.
- Config flow help text no longer suggests obsolete `NL:Q:` stop codes for RET.

### Changed

- **NS**: Destination now uses the API's `direction` field (falls back to the last route station).
- Replaced `pytz` with the standard library `zoneinfo`; dropped `aiohttp` and `pytz` from manifest requirements (aiohttp ships with Home Assistant).

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

[3.5.3]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.5.3
[3.5.2]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.5.2
[3.5.1]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.5.1
[3.5.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.5.0
[3.4.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.4.0
[3.3.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.3.0
[3.2.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.2.0
[3.1.2]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.1.2
[3.1.1]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.1.1
[3.1.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.1.0
[3.0.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v3.0.0
[2.1.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v2.1.0
[2.0.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v2.0.0
[1.1.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v1.1.0
[1.0.0]: https://github.com/rliessum/ov-travel-info/releases/tag/v1.0.0
