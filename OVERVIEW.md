# Integration Overview

## What You Get

This document provides a visual overview of what the RET & NS Departures integration provides in Home Assistant.

## Entities Created

For each configured stop or station, the integration creates **2 sensor entities**:

### 1. Next Departure Sensor

**Entity ID Pattern**: `sensor.<operator>_<location>_next_departure`

**Examples**:
- `sensor.ret_beurs_metro_next_departure`
- `sensor.ns_rotterdam_centraal_next_departure`

**State**: ISO timestamp of next departure (e.g., `2024-11-16T10:32:00+01:00`) or `Cancelled`

**Icon**: 
- `mdi:bus` for RET
- `mdi:train` for NS

**Attributes**:
```yaml
line: "2"                    # Line number / train type
operator: "RET"              # RET or NS
destination: "Nesselande"    # Final destination
platform: "1"                # Platform/track number
delay: 2                     # Delay in minutes (+ = late, - = early)
scheduled_time: "2024-11-16T10:30:00+01:00"
actual_time: "2024-11-16T10:32:00+01:00"
stop_name: "Beurs Metro"     # Friendly name
cancelled: false             # NS only
departures:                  # Array of next departures
  - line: "2"
    destination: "Nesselande"
    platform: "1"
    delay: 2
    scheduled_time: "2024-11-16T10:30:00+01:00"
    actual_time: "2024-11-16T10:32:00+01:00"
  - line: "25"
    destination: "Schiedam Centrum"
    platform: "2"
    delay: 0
    scheduled_time: "2024-11-16T10:35:00+01:00"
    actual_time: "2024-11-16T10:35:00+01:00"
  # ... up to max_departures
```

### 2. Time to Next Departure Sensor

**Entity ID Pattern**: `sensor.<operator>_<location>_time_to_next_departure`

**Examples**:
- `sensor.ret_beurs_metro_time_to_next_departure`
- `sensor.ns_rotterdam_centraal_time_to_next_departure`

**State**: Minutes until departure (integer, e.g., `8`)

**Unit**: `min`

**Icon**: `mdi:clock-outline`

**State Class**: `measurement`

**Attributes**: Same as Next Departure Sensor (for context)

## Device Grouping

All sensors from the same stop/station are grouped under a single device:

**Device Name**: `<OPERATOR> <Location Name>`
- Example: `RET Beurs Metro`
- Example: `NS Rotterdam Centraal`

**Device Info**:
- Manufacturer: RET or NS
- Model: `<OPERATOR> Departure Monitor`

## Example Dashboard Cards

### Basic Entity Card

```yaml
type: entities
title: Next Departures
entities:
  - entity: sensor.ret_beurs_metro_next_departure
  - entity: sensor.ret_beurs_metro_time_to_next_departure
```

**Display**:
```
Next Departures
┌─────────────────────────────────────┐
│ Next Departure         10:32:00     │
│ Time to Next Departure 8 min        │
└─────────────────────────────────────┘
```

### Enhanced Entity Card

```yaml
type: entities
title: Metro Line 2
entities:
  - type: custom:multiple-entity-row
    entity: sensor.ret_beurs_metro_next_departure
    name: To Nesselande
    state_header: Next
    secondary_info:
      attribute: actual_time
    format: time
    entities:
      - attribute: platform
        name: Platform
      - attribute: delay
        name: Delay
        unit: min
```

### Markdown Card (Departure Board Style)

```yaml
type: markdown
title: 🚆 Rotterdam Centraal
content: |
  {% set entity = 'sensor.ns_rotterdam_centraal_next_departure' %}
  {% for dep in state_attr(entity, 'departures')[:5] %}
  **{{ dep.line }}** to **{{ dep.destination }}**
  Platform {{ dep.platform }} • {{ ((as_timestamp(dep.actual_time) - now().timestamp()) / 60) | round(0) }} min
  {% if dep.delay > 0 %}⚠️ +{{ dep.delay }} min delay{% endif %}
  {% if dep.cancelled %}❌ CANCELLED{% endif %}
  ---
  {% endfor %}
```

**Display**:
```
🚆 Rotterdam Centraal
────────────────────────────────────
Intercity to Amsterdam Centraal
Platform 5 • 8 min

Sprinter to Den Haag Centraal  
Platform 3 • 12 min

Intercity to Utrecht Centraal
Platform 7 • 18 min ⚠️ +2 min delay
────────────────────────────────────
```

### Glance Card

```yaml
type: glance
title: Public Transport
entities:
  - entity: sensor.ret_beurs_metro_time_to_next_departure
    name: Metro
  - entity: sensor.ns_rotterdam_centraal_time_to_next_departure
    name: Train
```

### Conditional Card (Time-Based)

```yaml
type: conditional
conditions:
  - entity: sensor.ret_beurs_metro_time_to_next_departure
    state_not: unavailable
  - entity: sensor.ret_beurs_metro_time_to_next_departure
    state_not: unknown
conditions:
  - condition: numeric_state
    entity: sensor.ret_beurs_metro_time_to_next_departure
    below: 10
card:
  type: markdown
  content: |
    ## ⚠️ Your Metro Leaves Soon!
    Line {{ state_attr('sensor.ret_beurs_metro_next_departure', 'line') }}
    to {{ state_attr('sensor.ret_beurs_metro_next_departure', 'destination') }}
    in **{{ states('sensor.ret_beurs_metro_time_to_next_departure') }}** minutes
```

## Example Automations

### 1. Departure Alert

```yaml
automation:
  - alias: "Alert: Train Leaving"
    description: "Notify when train is leaving in 5 minutes"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ns_rotterdam_centraal_time_to_next_departure
        below: 5
    condition:
      - condition: state
        entity_id: person.your_name
        state: home
    action:
      - service: notify.mobile_app
        data:
          title: "🚂 Train Alert"
          message: >
            Your train to {{ state_attr('sensor.ns_rotterdam_centraal_next_departure', 'destination') }}
            leaves in {{ states('sensor.ns_rotterdam_centraal_time_to_next_departure') }} minutes
            from platform {{ state_attr('sensor.ns_rotterdam_centraal_next_departure', 'platform') }}!
```

### 2. Delay Notification

```yaml
automation:
  - alias: "Alert: Significant Delay"
    description: "Notify when departure has more than 5 min delay"
    trigger:
      - platform: state
        entity_id: sensor.ret_beurs_metro_next_departure
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.ret_beurs_metro_next_departure', 'delay') > 5 }}"
    action:
      - service: notify.mobile_app
        data:
          message: >
            Metro line {{ state_attr('sensor.ret_beurs_metro_next_departure', 'line') }}
            has a {{ state_attr('sensor.ret_beurs_metro_next_departure', 'delay') }} minute delay!
```

### 3. TTS Announcement

```yaml
automation:
  - alias: "Announce: Next Departure"
    description: "Announce next departure on Google Home"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: 'on'
    action:
      - service: tts.google_translate_say
        target:
          entity_id: media_player.living_room
        data:
          message: >
            Good morning. The next metro to work leaves in
            {{ states('sensor.ret_beurs_metro_time_to_next_departure') }} minutes
            from platform {{ state_attr('sensor.ret_beurs_metro_next_departure', 'platform') }}.
```

### 4. Smart Lighting

```yaml
automation:
  - alias: "Light: Time to Leave"
    description: "Flash lights when it's time to leave for the metro"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ret_home_stop_time_to_next_departure
        below: 8
    condition:
      - condition: time
        after: "07:00:00"
        before: "09:00:00"
        weekday:
          - mon
          - tue
          - wed
          - thu
          - fri
    action:
      - service: light.turn_on
        target:
          entity_id: light.hallway
        data:
          flash: long
      - delay: "00:00:02"
      - service: notify.mobile_app
        data:
          message: "Time to leave! Metro in {{ states('sensor.ret_home_stop_time_to_next_departure') }} min"
```

## Example Scripts

### Speak Next Departure

```yaml
script:
  speak_next_departure:
    alias: "Speak Next Departure"
    mode: single
    sequence:
      - service: tts.google_translate_say
        target:
          entity_id: media_player.living_room
        data:
          message: >
            {% set entity = 'sensor.ret_beurs_metro_next_departure' %}
            {% if states(entity) not in ['unknown', 'unavailable'] %}
              The next metro line {{ state_attr(entity, 'line') }}
              to {{ state_attr(entity, 'destination') }}
              leaves in {{ states('sensor.ret_beurs_metro_time_to_next_departure') }} minutes
              from platform {{ state_attr(entity, 'platform') }}.
              {% if state_attr(entity, 'delay') > 0 %}
                There is a {{ state_attr(entity, 'delay') }} minute delay.
              {% endif %}
            {% else %}
              No departure information available.
            {% endif %}
```

## Template Sensors

### Human-Readable Departure

```yaml
template:
  - sensor:
      - name: "Next Metro Info"
        state: >
          {% set entity = 'sensor.ret_beurs_metro_next_departure' %}
          {% if states(entity) not in ['unknown', 'unavailable', 'Cancelled'] %}
            Line {{ state_attr(entity, 'line') }} in {{ states('sensor.ret_beurs_metro_time_to_next_departure') }} min
          {% elif states(entity) == 'Cancelled' %}
            Cancelled
          {% else %}
            No info
          {% endif %}
        attributes:
          full_info: >
            {% set entity = 'sensor.ret_beurs_metro_next_departure' %}
            Line {{ state_attr(entity, 'line') }} to {{ state_attr(entity, 'destination') }}
            at {{ state_attr(entity, 'actual_time') | as_timestamp | timestamp_custom('%H:%M') }}
            from platform {{ state_attr(entity, 'platform') }}
```

### Combined Departures

```yaml
template:
  - sensor:
      - name: "All Next Departures"
        state: >
          {{ states('sensor.ret_beurs_metro_time_to_next_departure') }}
        attributes:
          departures: >
            {% set entities = [
              'sensor.ret_beurs_metro_next_departure',
              'sensor.ns_rotterdam_centraal_next_departure'
            ] %}
            {% set ns = namespace(deps=[]) %}
            {% for entity in entities %}
              {% if states(entity) not in ['unknown', 'unavailable'] %}
                {% set ns.deps = ns.deps + [{
                  'location': state_attr(entity, 'stop_name'),
                  'line': state_attr(entity, 'line'),
                  'destination': state_attr(entity, 'destination'),
                  'time': states(entity.replace('next_departure', 'time_to_next_departure')) ~ ' min'
                }] %}
              {% endif %}
            {% endfor %}
            {{ ns.deps }}
```

## Integration Status

You can check the integration status:

**Device Card**:
```yaml
type: entity
entity: sensor.ret_beurs_metro_next_departure
attribute: last_update
```

**Shows**: When data was last refreshed

## Tips for Best Display

1. **Use Groups**: Group multiple departure sensors by location
2. **Conditional Cards**: Show only when relevant (time-based, presence-based)
3. **Color Coding**: Use card-mod to color-code by delay
4. **Icons**: Customize icons based on transport type
5. **Badges**: Show time-to-departure as badges in dashboard header
6. **Mobile**: Create separate mobile-optimized views

## Icon Customization

Customize entity icons:

```yaml
customize:
  sensor.ret_beurs_metro_next_departure:
    icon: mdi:subway-variant
  sensor.ns_rotterdam_centraal_next_departure:
    icon: mdi:train-variant
```

Available transport icons:
- `mdi:subway` / `mdi:subway-variant`
- `mdi:tram`
- `mdi:bus`
- `mdi:train` / `mdi:train-variant`
- `mdi:ferry`

---

This integration provides rich, real-time departure information that can be displayed and automated in countless ways! 🚇🚊🚆
