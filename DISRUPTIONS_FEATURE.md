# 🚨 Disruption Monitoring Feature Added!

## Summary

The NS Disruptions monitoring feature has been successfully added to the RET & NS Departures integration!

## What's New

### New Binary Sensor

When enabled, NS stations now get a **disruption binary sensor**:

**Entity ID**: `binary_sensor.<station>_disruptions`

**State**: 
- `ON` - Active disruptions present
- `OFF` - No active disruptions

**Attributes**:
```yaml
disruptions:
  - disruption_id: "12345"
    title: "Verstoring Utrecht - Amsterdam"
    disruption_type: "DISRUPTION"
    impact: 4  # 0-5 scale
    phase: "In behandeling"
    cause: "Seinstoring"
    start: "2024-11-16T08:30:00+01:00"
    end: "2024-11-16T12:00:00+01:00"
    stations:
      - "Utrecht Centraal"
      - "Amsterdam Centraal"
    period: "vrijdag 16 november 08:30 - 12:00"
    expected_duration: "Tot ongeveer 12:00 uur"
count: 1  # Number of active disruptions
station_name: "Utrecht Centraal"
```

### Configuration

Enable disruption monitoring in the integration options:

1. Go to **Settings** → **Devices & Services**
2. Find your NS station integration
3. Click **Configure**
4. Enable **"Monitor disruptions and maintenance"**
5. Click **Submit**

The binary sensor will be created automatically after enabling.

## New Files Created

1. **`api_disruptions.py`** - NS Disruptions API client
2. **`binary_sensor.py`** - Disruption binary sensor entity

## Modified Files

1. **`const.py`** - Added disruption constants and endpoints
2. **`coordinator.py`** - Added disruption data fetching
3. **`__init__.py`** - Added binary_sensor platform
4. **`config_flow.py`** - Added disruption monitoring option
5. **`translations/en.json`** - Added English translations
6. **`translations/nl.json`** - Added Dutch translations
7. **`strings.json`** - Added option descriptions

## Features

✅ **Real-time Disruption Data** - Live updates from NS Disruptions API  
✅ **Active Filtering** - Only shows current disruptions  
✅ **Station-Specific** - Filter disruptions by station  
✅ **Rich Information** - Impact level, cause, affected stations, timing  
✅ **Optional** - Enable only when needed  
✅ **Same API Key** - Uses existing NS API key  
✅ **Device Grouping** - Groups with departure sensors  

## Disruption Types

The API provides three types:
- **DISRUPTION** - Unplanned disruptions
- **MAINTENANCE** - Planned maintenance
- **CALAMITY** - Major incidents

## Impact Levels

Scale from 0-5:
- **0-1**: Minimal impact
- **2-3**: Moderate impact
- **4-5**: Major impact

## Example Automations

### Notify on New Disruptions

```yaml
automation:
  - alias: "Alert: NS Disruption"
    trigger:
      - platform: state
        entity_id: binary_sensor.ns_rotterdam_centraal_disruptions
        from: 'off'
        to: 'on'
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ NS Disruption Alert"
          message: >
            {{ state_attr('binary_sensor.ns_rotterdam_centraal_disruptions', 'disruptions')[0]['title'] }}
            
            {{ state_attr('binary_sensor.ns_rotterdam_centraal_disruptions', 'disruptions')[0]['cause'] }}
```

### Display Disruptions on Dashboard

```yaml
type: conditional
conditions:
  - entity: binary_sensor.ns_rotterdam_centraal_disruptions
    state: 'on'
card:
  type: markdown
  title: ⚠️ Active Disruptions
  content: |
    {% for d in state_attr('binary_sensor.ns_rotterdam_centraal_disruptions', 'disruptions') %}
    **{{ d.title }}**
    - Type: {{ d.disruption_type }}
    - Impact: {{ d.impact }}/5
    - Cause: {{ d.cause }}
    - Period: {{ d.period }}
    ---
    {% endfor %}
```

### Conditional Departure Display

```yaml
type: entities
title: Rotterdam Centraal
entities:
  - type: conditional
    conditions:
      - entity: binary_sensor.ns_rotterdam_centraal_disruptions
        state: 'on'
    row:
      entity: binary_sensor.ns_rotterdam_centraal_disruptions
      name: ⚠️ Active Disruptions
      secondary_info: attribute
      attribute: count
  - entity: sensor.ns_rotterdam_centraal_next_departure
  - entity: sensor.ns_rotterdam_centraal_time_to_next_departure
```

### High Impact Alert

```yaml
automation:
  - alias: "Alert: High Impact Disruption"
    trigger:
      - platform: state
        entity_id: binary_sensor.ns_rotterdam_centraal_disruptions
    condition:
      - condition: template
        value_template: >
          {{ state_attr('binary_sensor.ns_rotterdam_centraal_disruptions', 'disruptions') | 
             selectattr('impact', 'ge', 4) | list | length > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Major NS Disruption"
          message: "High impact disruption detected at your station!"
          data:
            priority: high
```

## API Information

**Endpoint**: `https://gateway.apiportal.ns.nl/disruptions/v3`

**Authentication**: Uses same NS API key as departures

**Rate Limiting**: Standard NS API rate limits apply

**Polling**: Uses same 30-second interval as departures

## Benefits

1. **Stay Informed** - Know about disruptions before you leave
2. **Better Planning** - Adjust travel plans based on impact
3. **Automated Alerts** - Get notified when disruptions occur
4. **Historical Context** - See expected duration and recovery time
5. **Station-Specific** - Only relevant disruptions for your route

## Configuration Example

For an NS station with disruption monitoring:

```yaml
# Configuration via UI results in:
operator: ns
station_code: Rtd
station_name: Rotterdam Centraal
ns_api_key: your_api_key_here
# Options:
max_departures: 5
monitor_disruptions: true  # Enable disruption monitoring
```

## Performance Impact

- **Minimal** - Single additional API call per update cycle
- **Optional** - Only fetches when enabled
- **Efficient** - Cached with departure data
- **Resilient** - Failures don't affect departure sensors

## Notes

- Only available for NS stations (not RET)
- Requires valid NS API key
- Updates every 30 seconds (configurable)
- Gracefully handles API failures
- Disruptions appear/disappear based on active status

---

**Version**: 1.1.0  
**Feature**: NS Disruption Monitoring  
**Date**: November 16, 2024
