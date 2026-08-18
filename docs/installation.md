# Installation and Quick Start Guide

## Prerequisites

Before installing this integration, ensure you have:

1. **Home Assistant** 2024.11.0 or newer
2. **For NS departures**: A free API key from [NS API Portal](https://apiportal.ns.nl)
   - Create an account at https://apiportal.ns.nl
   - Subscribe to the **Ns-App** product (Reisinformatie + Stations API; it's free)
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
   - Examples: `beurs`, `rotterdam-centraal`, `provenierssingel`

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
   - If you already added an NS station, leave this empty to reuse that key (or type a different key)

2. **Location**: Defaults to your Home Assistant home. Nearby stations come from the [NS App Stations API](https://apiportal.ns.nl/api-details#api=nsapp-stations-api&operation=getNearestStations) (`getNearestStations`). Move the pin if you want stations near work or another place.

3. **Search by name or code** (optional): Type a name such as `Rotterdam` or a code such as `Rtd`. Leave empty to list stations nearest to the location.

4. Click **Submit**, then **select the station** from the list. Code and official name are filled in from the API.

5. **Monitor disruptions** (on by default): uses the [NS Disruptions API v3](https://apiportal.ns.nl/api-details#api=disruptions-api&operation=getDisruptions_v3) for this station. You can turn it off here or later in options.

6. Click **Submit** again to create the entry.

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
- **Test**: Open that URL in a browser. The page must show a departure board (Lijnen / Richting / Vertrektijd). A 404 or the notice “Op dit moment wordt er op deze lijn niet gereden” means the slug is wrong or the halt is out of service.
- **Note**: Use `rotterdam-centraal`, not `centraal-station`. RET's own search still offers `centraal-station`, but that page has no times.
- **Note**: Numeric `NL:Q:` codes from older docs are no longer used for RET
- **Works / diversions**: Confirm the current route on [Dienstregeling](https://www.ret.nl/). During the Hofplein works (until 22 November 2026) several tram stops including Schiekade have no departures; nearby replacement stops such as `provenierssingel` do.
- When a halt is empty, the next-departure entity is named **No service** and **What's wrong** shows the RET omleiding (replacement stop, period, and a link to the line timetable).

### NS: "Invalid API key" or no stations found

- **Solution**: Verify the API key is correct and the **Ns-App** product is subscribed
- **Check**: Ensure the key is active at https://apiportal.ns.nl
- **Search**: Type a station name (e.g. `Rotterdam`) instead of relying only on nearby results
- **Test**: Move the location pin closer to a Dutch station if nearest lookup is empty

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
