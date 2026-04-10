# RET & NS Departures for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Long-form documentation (install, architecture, dashboards): [docs/README.md](../../docs/README.md)

A Home Assistant custom integration that provides public transport departure information for:

- **RET** (Rotterdam Electric Tram): Metro, tram, and bus departures in the Rotterdam region
- **NS** (Nederlandse Spoorwegen): Train departures from Dutch railway stations

## Features

✅ **Real-time departure information** - Get up-to-date departure times, delays, and cancellations  
✅ **Multiple sensors** - Next departure time and time-to-departure in minutes  
✅ **Line filtering** - Filter RET departures by specific line numbers  
✅ **Rich attributes** - Line numbers, destinations, platforms, delays, and more  
✅ **UI configuration** - Easy setup through Home Assistant's configuration UI  
✅ **Async/await** - Non-blocking I/O for optimal Home Assistant performance  
✅ **Timezone-aware** - Proper handling of Europe/Amsterdam timezone and DST  
✅ **Bilingual** - English and Dutch translations included

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/ret_ns_departures` directory from this repository
2. Copy it to your Home Assistant's `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

#### For NS (Dutch Railways)
You'll need a free API key from NS:

1. Go to [NS API Portal](https://apiportal.ns.nl)
2. Create a free account
3. Subscribe to the "Reisinformatie API" (Travel Information API)
4. Copy your API key (Ocp-Apim-Subscription-Key)

#### For RET (Rotterdam)
No API key required. Departures are read from RET halt pages on [ret.nl](https://www.ret.nl); you configure the halt **URL slug** (see below).

### Setup via UI

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "RET & NS Departures"
3. Select your operator:
   - **RET** for Rotterdam metro/tram/bus
   - **NS** for Dutch trains

#### RET Configuration

- **Stop ID**: The halt slug from the RET URL `https://www.ret.nl/home/reizen/halte/<slug>.html` (e.g. `beurs`, `schiekade`, `centraal-station`)
- **Stop Name**: A friendly name (e.g., "Beurs Metro")
- **Line Filter** (optional): Comma-separated line numbers (e.g., `2, 25, E`)

#### NS Configuration

- **NS API Key**: Your API key from the NS API Portal
- **Station Code**: The NS station code
  - Common station codes:
    - `Rtd` - Rotterdam Centraal
    - `Asd` - Amsterdam Centraal
    - `Ut` - Utrecht Centraal
    - `Gvc` - Den Haag Centraal
    - `Ddr` - Dordrecht
  - Full list available at [NS Stations API](https://apiportal.ns.nl)
- **Station Name**: A friendly name (e.g., "Rotterdam Centraal")

### Options

After setup, you can configure additional options:

1. Go to **Settings** → **Devices & Services**
2. Find your RET or NS integration
3. Click "Configure"

Available options:
- **Maximum number of departures**: How many upcoming departures to track (default: 5)
- **Line Filter** (RET only): Update or change line filtering
- **Monitor disruptions** (NS only): Adds a **Disruptions** binary sensor when enabled ([details](../../docs/features/ns-disruptions.md))

## Entities

For each configured stop/station, the integration creates two departure sensors. NS entries can add a third entity when disruption monitoring is enabled:

### 1. Next Departure Sensor

**Entity ID**: `sensor.<operator>_<location>_next_departure`

**State**: ISO 8601 timestamp of the next departure (or "Cancelled" if the departure is cancelled)

**Attributes**:
- `line` - Line or train number
- `operator` - RET or NS
- `destination` - Final destination
- `platform` - Platform or track number
- `delay` - Delay in minutes (positive = late, negative = early)
- `scheduled_time` - Planned departure time
- `actual_time` - Expected departure time (including delays)
- `departures` - Array of upcoming departures with full details
- `stop_name` - Friendly name of the stop/station
- `cancelled` - Boolean indicating if departure is cancelled (NS only)

### 2. Time to Next Departure Sensor

**Entity ID**: `sensor.<operator>_<location>_time_to_next_departure`

**State**: Minutes until the next departure (integer)

**Unit**: `min`

**Attributes**: Same as Next Departure Sensor

### 3. Disruptions (NS only, optional)

**Name**: Disruptions · **Type**: binary sensor · **Device class**: `problem` · **ON** when active disruptions apply to the configured station. See [NS disruptions](../../docs/features/ns-disruptions.md).

## Example Automations

### Alert When Next Train is Leaving Soon

```yaml
automation:
  - alias: "Notify: Train Leaving in 5 Minutes"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ns_rotterdam_centraal_time_to_next_departure
        below: 5
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.ns_rotterdam_centraal_next_departure', 'destination') == 'Amsterdam Centraal' }}"
    action:
      - service: notify.mobile_app
        data:
          message: "Your train to Amsterdam leaves in {{ states('sensor.ns_rotterdam_centraal_time_to_next_departure') }} minutes from platform {{ state_attr('sensor.ns_rotterdam_centraal_next_departure', 'platform') }}!"
```

### Flash Lights When Metro is Approaching

```yaml
automation:
  - alias: "Flash Lights: Metro in 3 Minutes"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ret_beurs_metro_time_to_next_departure
        below: 3
    action:
      - service: light.turn_on
        target:
          entity_id: light.hallway
        data:
          flash: short
```

### Display Departures on Dashboard

```yaml
type: entities
title: Next Departures
entities:
  - entity: sensor.ret_beurs_metro_next_departure
    type: custom:multiple-entity-row
    name: Metro Line 2
    state_header: Leaves in
    secondary_info:
      attribute: destination
    entities:
      - attribute: delay
        name: Delay
        unit: min
  - entity: sensor.ns_rotterdam_centraal_next_departure
    type: custom:multiple-entity-row
    name: Intercity
    secondary_info:
      attribute: destination
    entities:
      - attribute: platform
        name: Platform
```

## Use Cases

### 1. Morning Commute Assistant

Monitor your regular metro/train and get notifications when it's time to leave:

```yaml
automation:
  - alias: "Time to Leave for Work"
    trigger:
      - platform: template
        value_template: >
          {{ states('sensor.ret_home_stop_time_to_next_departure') | int - 5 <= 
             (now().hour * 60 + now().minute) - 
             (states.input_datetime.commute_walk_time.attributes.hour * 60 + 
              states.input_datetime.commute_walk_time.attributes.minute) }}
    action:
      - service: tts.google_say
        data:
          message: "Time to leave! Your metro leaves in {{ states('sensor.ret_home_stop_time_to_next_departure') }} minutes."
```

### 2. Smart Display Board

Create a digital departure board for your hallway:

```yaml
type: markdown
content: >
  # 🚆 Departures from Rotterdam Centraal
  
  {% for dep in state_attr('sensor.ns_rotterdam_centraal_next_departure', 'departures')[:3] %}
  **{{ dep.line }}** to **{{ dep.destination }}** - Platform {{ dep.platform }}
  
  Leaves in: {{ ((as_timestamp(dep.actual_time) - now().timestamp()) / 60) | round(0) }} min
  {% if dep.delay > 0 %}⚠️ +{{ dep.delay }} min delay{% endif %}
  
  ---
  {% endfor %}
```

### 3. Presence-Based Automation

Turn on heating when you're on your way home:

```yaml
automation:
  - alias: "Start Heating: On Train Home"
    trigger:
      - platform: state
        entity_id: sensor.ns_amsterdam_centraal_next_departure
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.ns_amsterdam_centraal_next_departure', 'destination') == 'Rotterdam Centraal' }}"
      - condition: numeric_state
        entity_id: sensor.ns_amsterdam_centraal_time_to_next_departure
        below: 45
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room
        data:
          temperature: 21
```

## API Information

### RET (ret.nl)

RET data is loaded from the public halt timetable pages on [ret.nl](https://www.ret.nl). No API key is required.

**Polling**: Default 30 seconds (minimum 15). Scraping may break if RET changes page markup—open an issue if that happens.

### NS (Dutch Railways)

This integration uses the official [NS Reisinformatie API](https://apiportal.ns.nl).

**API Key**: Free API key required (sign up at https://apiportal.ns.nl)

**Rate Limiting**: Standard rate limits apply as per NS API terms. Default polling interval is 30 seconds.

**Data Coverage**: All NS stations in the Netherlands.

## Troubleshooting

### Integration doesn't show up after installation

1. Make sure you've copied the files to the correct location: `config/custom_components/ret_ns_departures/`
2. Restart Home Assistant
3. Check the logs for any errors: **Settings** → **System** → **Logs**

### No departures showing

**For RET**:
- Verify the halt slug matches a working URL on ret.nl
- Some halts may have no departures at certain times
- Check if line filtering is excluding all departures

**For NS**:
- Verify your API key is valid at [NS API Portal](https://apiportal.ns.nl)
- Check your station code is correct
- Ensure you have an active internet connection
- Check API rate limits haven't been exceeded

### Entities unavailable

- Check your internet connection
- For NS: verify your API key hasn't expired
- Check Home Assistant logs for specific errors
- Restart the integration: **Settings** → **Devices & Services** → **RET & NS Departures** → **⋮** → **Reload**

### TimeoutError in logs

The integration times out after 10 seconds. This usually indicates:
- Network connectivity issues
- API service is temporarily down
- High latency to the API endpoints

The integration will automatically retry on the next update cycle.

## Development

### Running Tests

Use a virtual environment and a Python version supported by `pytest-homeassistant-custom-component` (see Home Assistant dev docs). From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
pytest tests/
```

Layout and API details: [architecture.md](../../docs/architecture.md).

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/rliessum/ov-travel-info/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rliessum/ov-travel-info/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [NS](https://www.ns.nl) for the official travel information API
- [RET](https://www.ret.nl) for public timetable pages
- Home Assistant community for documentation and examples

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by RET or NS. Use at your own risk.

---

Made with ❤️ for the Home Assistant community
