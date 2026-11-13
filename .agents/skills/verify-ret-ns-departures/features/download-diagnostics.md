# Download diagnostics

A user downloads a diagnostics file for a stop or station to attach to a bug report. The file shows the entry's settings and its latest fetched data, with the NS API key removed and the train picture replaced by its size.

## Sub-features

- `diag-ret` returns the settings and latest departures for a RET entry.
- `diag-ns` returns the same for an NS entry, with disruptions and train details.
- `diag-redacted` hides the NS API key.
- `diag-no-image` reports the train picture as a byte count only.

## How to get to it (user POV)

- Settings, Devices & services, RET & NS Departures, the entry's menu, then Download diagnostics.

## Driving it with ha_verify.py

Preconditions:

- Doctor exits `0`.
- The entry `RET Beurs` exists, created per [Add a RET stop](./add-ret-stop.md).
- For the NS bullets, the entry `NS Rotterdam Centraal` exists, created per [Add an NS station](./add-ns-station.md).

- **Find entries.** Run `V api --run <run-id> --label diag-entries GET "/api/config/config_entries/entry?domain=ret_ns_departures"`. Take the `entry_id` of each entry.
- **RET file.** Run `V api --run <run-id> --label diag-ret GET /api/diagnostics/config_entry/<entry_id>` for `RET Beurs`. The response has `data.entry.data` with `operator` `ret`, `stop_id` `beurs`, and `stop_name` `Beurs`. `data.coordinator` has `last_update_success` `true`, `update_interval` `0:00:30`, `train_image_bytes` `0`, and `data.departures`.
- **NS file.** Run the same call with label `diag-ns` for `NS Rotterdam Centraal`. `data.entry.data` has `station_code` `RTD`, and `data.entry.options` has `monitor_disruptions`. `data.coordinator.data` has `departures` and `disruptions`.
- **Key is hidden.** In the `diag-ns` response, `data.entry.data.ns_api_key` is `**REDACTED**`.
- **Picture is a size.** In the `diag-ns` response, `data.coordinator.train_image_bytes` is a positive number once the image entity has a timestamp state, and `data.coordinator.data` has no `train_image` key.

## Gotchas

- The route takes the `entry_id` only. Do not add the domain to the path.
- The helper redacts the key from evidence too. `**REDACTED**` is the integration's own redaction, and `<redacted>` is the helper's. Seeing `<redacted>` in a diagnostics file means the integration leaked the key.
- `train_image_bytes` is `0` for an NS entry whose image entity is `unavailable`. That follows the image, not diagnostics.
- The file also carries Home Assistant's own sections, such as `home_assistant` and `integration_manifest`. Assert only on `data`.
