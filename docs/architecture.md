# RET & NS Departures Integration - File Structure

This document provides an overview of the complete integration structure.

## Directory Structure

```
ov-travel-info/
├── custom_components/
│   └── ret_ns_departures/
│       ├── __init__.py                 # Integration setup and entry point
│       ├── manifest.json               # Integration metadata
│       ├── const.py                    # Constants and configuration keys
│       ├── config_flow.py              # UI configuration flow
│       ├── coordinator.py              # Data update coordinator
│       ├── sensor.py                   # Departure sensor entities
│       ├── binary_sensor.py            # NS disruption binary sensor (optional)
│       ├── api_ret.py                  # RET client (ret.nl HTML)
│       ├── api_ret_diversions.py       # RET omleidingen parse/match
│       ├── api_ns.py                   # NS departures API client
│       ├── api_disruptions.py          # NS disruptions API client
│       ├── api_virtual_train.py        # NS Virtual Train getImage client
│       ├── api_spoorkaart.py           # NS Spoorkaart getStoring client
│       ├── disruption_info.py          # Readable disruption titles and summaries
│       ├── image.py                    # Next-train image entity
│       ├── icons.json                  # State icons
│       ├── brand/                      # HACS / HA icon and logo (OV-chipkaart mark)
│       ├── translations/
│       │   ├── en.json                 # English translations
│       │   └── nl.json                 # Dutch translations
│       ├── strings.json                # UI strings
│       └── README.md                   # Integration readme (HACS)
├── brand/                              # Repo-level HACS brand assets (icon.png)
├── docs/                               # All long-form documentation
├── tests/
│   ├── conftest.py                     # Pytest configuration
│   ├── test_api_ret.py                 # RET client tests
│   ├── test_api_ret_diversions.py      # RET omleidingen matching
│   ├── test_api_ns.py                  # NS API tests
│   ├── test_config_flow.py             # Config flow tests
│   └── …                               # coordinator, sensor, binary_sensor, others
├── README.md                           # Repository entry point
├── LICENSE                             # MIT License
├── CHANGELOG.md                        # Version history
├── requirements_test.txt               # Test dependencies
├── pytest.ini                          # Pytest configuration
├── example_configuration.yaml          # Example HA configuration
├── hacs.json                           # HACS default metadata
└── .gitignore                          # Git ignore rules
```

## Key Components

### Core Integration Files

1. **`__init__.py`**
   - Integration entry point
   - Handles setup and unload of config entries
   - Creates coordinator instance
   - Forwards setup to sensor, binary_sensor, and image platforms

2. **`manifest.json`**
   - Integration metadata
   - Domain, name, version
   - Dependencies (`beautifulsoup4`; aiohttp ships with Home Assistant)
   - Documentation links

3. **`const.py`**
   - Domain constant
   - Configuration keys
   - Default values
   - API endpoints
   - Attribute names

### Configuration

4. **`config_flow.py`**
   - UI configuration flow
   - Operator selection (RET/NS)
   - Stop/station validation
   - Options flow for updates

### Data Management

5. **`coordinator.py`**
   - DataUpdateCoordinator implementation
   - Manages API polling
   - Error handling
   - Data refresh logic

6. **`api_ret.py`**
   - RET client: fetches halt HTML from ret.nl and parses departures (BeautifulSoup)
   - Stop “ID” is the URL slug (e.g. `beurs`)

7. **`api_ns.py`**
   - NS Reisinformatie API client (departures)
   - NS App Stations API (`getNearestStations` + name search) for config-flow lookup
   - Handles authentication
   - Station validation

8. **`api_disruptions.py`**
   - NS disruptions endpoint (same API key as departures)
   - Used when monitoring is enabled

8b. **`api_spoorkaart.py`**
   - NS Spoorkaart `getStoring` (GeoJSON for a disruption id)
   - Used to attach map location to monitored disruptions

### Entities

9. **`sensor.py`**
   - Next departure and time-to-next-departure sensors
   - Rich attributes and device grouping

10. **`binary_sensor.py`**
   - NS “Disruptions” sensor when `monitor_disruptions` is enabled
   - RET service-notice sensor (omleidingen when the halt board is empty)

### Localization

11. **`translations/en.json`** & **`translations/nl.json`**
   - UI text translations
   - Error messages
   - Configuration descriptions

12. **`strings.json`**
    - UI strings with descriptions
    - Field explanations

## Features Summary

### RET Integration
- ✅ Metro/tram/bus departures from ret.nl timetable pages
- ✅ Line filtering support
- ✅ No API key required
- ✅ Delay information (when present in page)
- ✅ No dependency on third-party OVapi

### NS Integration
- ✅ Train departures via NS Reisinformatie API
- ✅ Optional active-disruption binary sensor
- ✅ Cancellation detection
- ✅ Delay and platform/track information
- ✅ Train type and number where provided

### Technical Features
- ✅ Async/await throughout
- ✅ Non-blocking I/O
- ✅ DataUpdateCoordinator
- ✅ Timezone-aware (Europe/Amsterdam)
- ✅ Error handling and retry logic
- ✅ Comprehensive logging
- ✅ Type hints
- ✅ Unit tests
- ✅ Config flow validation

### Home Assistant Integration
- ✅ UI configuration
- ✅ Options flow
- ✅ Device grouping
- ✅ Entity naming
- ✅ Rich attributes
- ✅ State classes
- ✅ Icons
- ✅ Translations (EN/NL)

## Testing

The integration includes comprehensive unit tests:

- **`test_api_ret.py`**: Tests for RET API client
  - Successful data retrieval
  - Line filtering
  - Error handling
  - Stop validation

- **`test_api_ns.py`**: Tests for NS API client
  - Successful data retrieval
  - Cancellation handling
  - API key authentication
  - Station validation
  - Nearest-station and name search parsing (v2/v3 payloads)

- **`test_api_spoorkaart.py`**: Tests for Spoorkaart getStoring
  - GeoJSON centroid / bbox parsing
  - 404 and missing-subscription handling
  - Per-disruption cache

- **`test_coordinator.py`**: Coordinator update paths, including disruption + getStoring enrichment

- **`test_config_flow.py`**: Tests for configuration flow
  - User flow
  - RET configuration
  - NS configuration
  - Validation errors

## Dependencies

### Runtime
- `beautifulsoup4>=4.12.0` - RET HTML parsing
- `aiohttp` - shipped with Home Assistant

### Testing
- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-homeassistant-custom-component>=0.13.0` - HA test utilities

## API Information

### RET (ret.nl)
- **Source**: `https://www.ret.nl/home/reizen/halte/{slug}.html`
- **Authentication**: None
- **Format**: HTML (scraped)
- **Coverage**: RET halts exposed on the website

### NS (Dutch Railways)
- **Departures**: `https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2`
- **Stations lookup**: `https://gateway.apiportal.ns.nl/nsapp-stations/v2` (`/nearest` and `?q=`)
- **Disruptions**: `https://gateway.apiportal.ns.nl/disruptions/v3` (`getDisruptions_v3`); fallback `reisinformatie-api/api/v3/disruptions`
- **Virtual Train**: `https://gateway.apiportal.ns.nl/virtual-train-api/api/v1` (`getImage` for the next departure)
- **Spoorkaart**: `https://gateway.apiportal.ns.nl/Spoorkaart-API/api/v1` (`getStoring` GeoJSON for a disruption id)
- **Authentication**: API key via header (`Ocp-Apim-Subscription-Key`)
- **Format**: JSON

## Configuration Examples

### RET Stop Configuration
```yaml
Stop ID: beurs                    # slug from ret.nl halt URL (not centraal-station)
Stop Name: Beurs Metro
Line Filter: 2, 25, E (optional)
```

### NS Station Configuration
```yaml
API Key: your-ns-api-key
# Config flow looks up code + official name via NS App Stations API
# (nearest to a map location, or search by name)
Station Code: RTD
Station Name: Rotterdam Centraal
```

## Entity Naming

Entities follow this pattern:
- `sensor.<operator>_<location>_next_departure`
- `sensor.<operator>_<location>_time_to_next_departure`

Examples:
- `sensor.ret_beurs_metro_next_departure`
- `sensor.ns_rotterdam_centraal_time_to_next_departure`

## Future Enhancements

Potential improvements for future versions:
- Support for more transport operators (GVB, HTM, etc.)
- Platform change alerts
- Journey planning integration
- Historical delay statistics
- Custom update intervals per stop/station
- Binary sensors for specific events
- Service to refresh data on demand

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Ensure all tests pass
6. Submit a pull request

## Support

- Report issues on GitHub
- Join discussions for questions
- Check documentation for common problems
- Review logs for troubleshooting

---

**Home Assistant**: 2024.11.0+ (`hacs.json`)
**License**: MIT
