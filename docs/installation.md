# Installation and Quick Start Guide

## Prerequisites

Before installing this integration, ensure you have:

1. **Home Assistant** 2024.1.0 or newer
2. **For NS departures**: A free API key from [NS API Portal](https://apiportal.ns.nl)
   - Create an account at https://apiportal.ns.nl
   - Subscribe to the "Reisinformatie API" (it's free)
   - Copy your API key (listed as "Ocp-Apim-Subscription-Key")
3. **For RET departures**: No API key needed!

## Installation Methods

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click on **Integrations**
3. Click the **⋮** menu (three dots) in the top right
4. Select **Custom repositories**
5. Add repository URL: `https://github.com/rliessum/ov-travel-info`
6. Select category: **Integration**
7. Click **Add**
8. Find "RET & NS Departures" in HACS and click **Download**
9. **Restart Home Assistant**

### Method 2: Manual Installation

1. Download the latest release from GitHub
2. Extract the zip file
3. Copy the `custom_components/ret_ns_departures` folder to your Home Assistant's `config/custom_components/` directory
   ```
   config/
   └── custom_components/
       └── ret_ns_departures/
           ├── __init__.py
           ├── manifest.json
           ├── ...
   ```
4. **Restart Home Assistant**

## Configuration

### Step 1: Add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration** (bottom right)
3. Search for "RET & NS Departures"
4. Click on it to start configuration

### Step 2: Choose Operator

Select which transport operator you want to configure:
- **RET** - Rotterdam metro, tram, bus
- **NS** - Dutch trains

### Step 3a: Configure RET (Rotterdam)

If you selected RET:

1. **Stop ID**: Enter the URL slug for the halt on the RET website (not a numeric OVapi code).
   - Open a halt in the browser, e.g. `https://www.ret.nl/home/reizen/halte/beurs.html`
   - Use only the slug: `beurs` (lowercase; use hyphens exactly as in the URL).
   - Examples: `beurs`, `schiekade`, `centraal-station`

2. **Stop Name**: Enter a friendly name
   - Example: "Beurs Metro" or "Home Stop"
   - This will be used in device and entity names

3. **Line Filter** (optional): Enter specific line numbers
   - Format: `2, 25, E` (comma-separated)
   - Leave empty to show all lines
   - Example: `2` (only metro line 2)
   - Example: `2, 25` (metro 2 and tram 25)

4. Click **Submit**

### Step 3b: Configure NS (Dutch Trains)

If you selected NS:

1. **NS API Key**: Enter your NS API key
   - Get it from https://apiportal.ns.nl
   - Look for "Ocp-Apim-Subscription-Key"

2. **Station Code**: Enter the NS station code
   - Format: `Rtd`, `Asd`, `Ut`, etc.
   
   **Common station codes**:
   - `Rtd` - Rotterdam Centraal
   - `Asd` - Amsterdam Centraal
   - `Ut` - Utrecht Centraal
   - `Gvc` - Den Haag Centraal
   - `Ddr` - Dordrecht
   - `Ehv` - Eindhoven Centraal
   - `Ah` - Alkmaar
   - `Zl` - Zwolle
   
   Find more codes at: https://apiportal.ns.nl/docs/services/reisinformatie-api/operations/getStations

3. **Station Name**: Enter a friendly name
   - Example: "Rotterdam Centraal" or "Work Station"

4. Click **Submit**

## Verification

After configuration, you should see:

1. A new device in **Settings** → **Devices & Services** → **RET & NS Departures**
2. Two sensor entities:
   - `sensor.<operator>_<location>_next_departure`
   - `sensor.<operator>_<location>_time_to_next_departure`

Example:
- `sensor.ret_beurs_metro_next_departure`
- `sensor.ret_beurs_metro_time_to_next_departure`

## Configuring Options

To update settings after initial configuration:

1. Go to **Settings** → **Devices & Services**
2. Find "RET & NS Departures"
3. Click **Configure** on your integration
4. Update:
   - **Maximum departures**: Number of departures to track (default: 5)
   - **Line Filter** (RET only): Update line filtering
   - **Monitor disruptions** (NS only): Toggle the optional disruption binary sensor

## Adding Multiple Stops/Stations

To monitor multiple stops or stations:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Select "RET & NS Departures" again
4. Configure the new stop/station
5. Repeat for each stop/station you want to monitor

Each stop/station will create separate sensor entities.

## Using the Sensors

### In the Dashboard

Add to your Lovelace dashboard:

```yaml
type: entities
title: Public Transport
entities:
  - entity: sensor.ret_beurs_metro_next_departure
    type: attribute
    attribute: destination
    name: Next Metro
  - entity: sensor.ret_beurs_metro_time_to_next_departure
    name: Leaves in
```

### In Automations

Create automations based on departures:

```yaml
automation:
  - alias: "Leave for Train"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ns_rotterdam_centraal_time_to_next_departure
        below: 10
    action:
      - service: notify.mobile_app
        data:
          message: "Your train leaves in 10 minutes!"
```

### In Templates

Use in template sensors:

```yaml
template:
  - sensor:
      - name: "Next Departure Info"
        state: >
          Line {{ state_attr('sensor.ret_beurs_metro_next_departure', 'line') }} 
          to {{ state_attr('sensor.ret_beurs_metro_next_departure', 'destination') }}
          in {{ states('sensor.ret_beurs_metro_time_to_next_departure') }} min
```

## Troubleshooting

### Integration doesn't appear in Add Integration

- **Solution**: Clear browser cache and restart Home Assistant
- **Check**: Ensure files are in `config/custom_components/ret_ns_departures/`
- **Verify**: Check Home Assistant logs for errors

### RET: "Invalid stop ID" or no departures

- **Solution**: Use the halt slug from `https://www.ret.nl/home/reizen/halte/<slug>.html`
- **Test**: Open that URL in a browser; if it 404s, the slug is wrong
- **Note**: Numeric `NL:Q:` codes from older docs are no longer used for RET

### NS: "Invalid station code or API key" error

- **Solution**: Verify API key is correct
- **Check**: Ensure API key is active at https://apiportal.ns.nl
- **Verify**: Station code is correct (case-sensitive)
- **Test**: Try a common code like `Rtd` first

### No departures showing

- **Check**: Internet connection is working
- **RET**: Some halts may have no departures at certain times; confirm the page loads on ret.nl
- **NS**: Ensure station code is correct
- **Look**: Check if line filter is excluding all departures
- **Wait**: Give it a few minutes - first fetch might take up to 30 seconds

### Entities show "Unavailable"

- **Check**: Integration status in Devices & Services
- **Try**: Reload integration:
  - Go to **Settings** → **Devices & Services**
  - Find your integration
  - Click **⋮** → **Reload**
- **Review**: Home Assistant logs for specific errors
- **Test**: Disable and re-enable the integration

### High delay values or incorrect times

- **Check**: Your Home Assistant timezone is set correctly
- **Verify**: System time is accurate
- **Ensure**: Europe/Amsterdam timezone is being used

## Getting Help

If you encounter issues:

1. **Check Logs**: Settings → System → Logs
2. **Enable Debug Logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.ret_ns_departures: debug
   ```
3. **Report Issues**: https://github.com/rliessum/ov-travel-info/issues
4. **Discussions**: https://github.com/rliessum/ov-travel-info/discussions

When reporting issues, include:
- Home Assistant version
- Integration version
- Relevant log entries
- Configuration details (without API keys!)

## Next Steps

- Review the [repository README](../README.md) and [overview](overview.md) for dashboards and automations
- Check [example_configuration.yaml](../example_configuration.yaml) for YAML ideas
- Read [architecture.md](architecture.md) for technical layout

## Tips

1. **Polling Interval**: Default is 30 seconds - suitable for most users
2. **API Limits**: NS API has rate limits - don't set too many stations or too short intervals
3. **Line Filtering**: Use for busy stops to reduce clutter
4. **Multiple Stops**: Monitor your home stop, work stop, and frequently used stations
5. **Automations**: Combine with location tracking for smart departure notifications

---
