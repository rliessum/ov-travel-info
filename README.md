# RET & NS Departures for Home Assistant

A Home Assistant custom integration for real-time public transport departures in the Netherlands.

**Repository:** [github.com/rliessum/ov-travel-info](https://github.com/rliessum/ov-travel-info)

## Features

- **RET** (Rotterdam): Metro, tram, and bus departures from [ret.nl](https://www.ret.nl) halt pages
- **NS** (Dutch Railways): Train departures via the official NS API; optional **disruption** binary sensor
- **Config flow** setup, multiple stops/stations, line filtering (RET), rich sensor attributes
- **Async** coordinator-based updates; Europe/Amsterdam–aware times

## Quick start

1. Install via [HACS](https://www.hacs.xyz/) or copy `custom_components/ret_ns_departures` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. **Settings** → **Devices & services** → **Add integration** → search **RET & NS Departures**

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/README.md](docs/README.md) | Index of all documentation |
| [docs/installation.md](docs/installation.md) | Install, UI steps, troubleshooting |
| [docs/overview.md](docs/overview.md) | Entities, Lovelace examples, automations |
| [docs/architecture.md](docs/architecture.md) | Code layout, APIs, tests |
| [docs/features/ns-disruptions.md](docs/features/ns-disruptions.md) | NS disruption monitoring |
| [custom_components/ret_ns_departures/README.md](custom_components/ret_ns_departures/README.md) | Integration readme (shown in HACS) |

## Requirements

- Home Assistant 2024.1.0 or newer
- **NS**: Free API key from [NS API Portal](https://apiportal.ns.nl) (Reisinformatie API)
- **RET**: No API key; use the halt **slug** from the ret.nl URL (see [docs/installation.md](docs/installation.md))

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
