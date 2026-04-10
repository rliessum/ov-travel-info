# Documentation

All user and maintainer documentation for **RET & NS Departures** lives here. The repository root [README.md](../README.md) is the short entry point for GitHub and clones.

| Document | Audience | Description |
|----------|----------|-------------|
| [installation.md](installation.md) | Users | HACS/manual install, UI setup, troubleshooting |
| [overview.md](overview.md) | Users | Entities, dashboards, automations, templates |
| [architecture.md](architecture.md) | Developers | Layout of `custom_components`, APIs, tests |
| [features/ns-disruptions.md](features/ns-disruptions.md) | Users | Optional NS disruption binary sensor |
| [internal/ret-data-source.md](internal/ret-data-source.md) | Maintainers | Why RET uses the website instead of OVapi |

## Version and changelog

- Released versions: [CHANGELOG.md](../CHANGELOG.md) (root; Keep a Changelog)
- Current integration version: `custom_components/ret_ns_departures/manifest.json` → `version`

## Maintainer notes (audit snapshot)

- **RET data**: Fetched by scraping `https://www.ret.nl/home/reizen/halte/{slug}.html`, not OVapi. Configure **stop ID** as the URL slug (e.g. `beurs`, `schiekade`, `centraal-station`).
- **NS departures**: NS Reisinformatie API v2; disruptions use the v3 path configured in `const.py`.
- **Entities**: Each entry creates two departure sensors; NS entries may add a **Disruptions** binary sensor when the option is enabled.
- **Tests**: `tests/test_api_ret.py`, `test_api_ns.py`, `test_config_flow.py` — no separate `test_ret_scraping.py` in tree.
