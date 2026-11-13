# Configure an entry

A user opens Configure on an existing stop or station and changes how many departures are kept, which RET lines are shown, or whether NS disruptions are monitored. The entry reloads and the entities reflect the change.

## Sub-features

- `opt-form-ret` shows `max_departures` and `line_filter` for a RET entry.
- `opt-form-ns` shows `max_departures` and `monitor_disruptions` for an NS entry.
- `opt-line-filter` limits a RET stop's departures to the listed lines.
- `opt-max-departures` caps the `departures` list.
- `opt-max-range` rejects a value outside 1 to 20.
- `opt-ns-disruptions-off` removes the NS disruption sensor.

## How to get to it (user POV)

- Settings, Devices & services, RET & NS Departures, then Configure on the entry.

## Driving it with ha_verify.py

Preconditions:

- Doctor exits `0`.
- The entry `RET Beurs` exists, created per [Add a RET stop](./add-ret-stop.md).
- For the NS bullets, the entry `NS Rotterdam Centraal` exists with disruptions monitored.

- **Capture before.** Run `V api --run <run-id> --label opt-before-ret GET /api/states`. Note a line that appears at least twice in the `sensor.ret_beurs_next_departure` `departures` list, or the last one listed. The recipe below uses `1`.
- **Find entry.** Run `V api --run <run-id> --label opt-entries GET "/api/config/config_entries/entry?domain=ret_ns_departures"`. Take `entry_id` from the item whose `title` is `RET Beurs`.
- **Open Configure.** Run `V api --run <run-id> --label opt-form-ret POST /api/config/config_entries/options/flow '{"handler":"<entry_id>"}'`. The response has `step_id` `init` with `max_departures` defaulting to `5` and bounded by `valueMin` `1` and `valueMax` `20`, and `line_filter` defaulting to an empty string.
- **Out of range.** Run `V api --run <run-id> --label opt-max-zero POST /api/config/config_entries/options/flow/<flow_id> '{"max_departures":0}'`. The response is HTTP 400 with `errors` `{"max_departures": "value must be at least 1"}`, and the helper exits `1`. The flow stays open.
- **Save options.** Run `V api --run <run-id> --label opt-save-ret POST /api/config/config_entries/options/flow/<flow_id> '{"max_departures":2,"line_filter":"1"}'`. The response has `type` `create_entry`.
- **Confirm effect.** Wait 8 seconds, then run `V api --run <run-id> --label opt-effect-ret GET /api/states`. The `sensor.ret_beurs_next_departure` `departures` list has at most 2 items and every item has `line` `1`.
- **Confirm stored value.** Repeat Open Configure with label `opt-reopen-ret`. The defaults now read `2` and `1`.
- **NS form.** Open Configure on the NS entry with label `opt-form-ns`. The form has `max_departures` and `monitor_disruptions`, and no `line_filter`.
- **Disruptions off.** Submit `{"max_departures":5,"monitor_disruptions":false}` with label `opt-ns-disruptions-off`. After 8 seconds `GET /api/states` has no `binary_sensor.ns_rotterdam_centraal_disruptions`, while the departure sensors and the image keep live values.

## Gotchas

- Saving options reloads the entry. Reading states too early returns the old values or `unavailable`.
- Do not filter on the first departure in the list. It can leave during the reload, and the sensor then reads `unknown` with an empty list. That happened with line `C` in the proving run.
- The filter is a comma-separated string, such as `"2, 8, E"`. It is not a JSON array.
- A disruption sensor that lingers as `unavailable` after the toggle is a regression.
- Reloading an NS entry refetches the train image, so its timestamp changes after an options save.
