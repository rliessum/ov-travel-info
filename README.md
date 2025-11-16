# RET & NS Departures for Home Assistant

A production-ready Home Assistant custom integration for real-time public transport departure information in the Netherlands.

## Features

- **RET** (Rotterdam): Real-time metro, tram, and bus departures
- **NS** (Dutch Railways): Real-time train departures from all Dutch stations
- **Easy UI configuration** via Home Assistant's config flow
- **Multiple sensors** per stop/station with rich attributes
- **Line filtering** for RET departures
- **Timezone-aware** with proper DST handling
- **Async/non-blocking** for optimal Home Assistant performance

## Quick Start

1. Install via HACS or manually copy `custom_components/ret_ns_departures` to your config directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "RET & NS Departures"
5. Configure your stops/stations

## Documentation

Full documentation is available in [`custom_components/ret_ns_departures/README.md`](custom_components/ret_ns_departures/README.md)

## Requirements

- Home Assistant 2024.1.0 or newer
- For NS: Free API key from [NS API Portal](https://apiportal.ns.nl)
- For RET: No API key needed

## Support

- [Report Issues](https://github.com/yourusername/ret-ns-departures/issues)
- [Discussions](https://github.com/yourusername/ret-ns-departures/discussions)

## License

MIT License - See [LICENSE](LICENSE) file for details.
# ov-travel-info
