# Add a RET stop

A user adds a Rotterdam RET stop by its ret.nl halt slug and gets a next-departure sensor, a minutes-to-departure sensor, and a service-notice binary sensor for that stop.

## Sub-features

- `ret-add-form` shows the operator choice, then the RET form.
- `ret-add-invalid` rejects an unknown slug with a field error.
- `ret-add-traversal` rejects a stop ID that is not a plain slug.
- `ret-add-create` creates the entry `RET <stop name>`.
- `ret-add-entities` exposes the three entities with live values.
- `ret-add-duplicate` refuses the same stop twice.
- `ret-add-filter` accepts an optional line filter at creation.

## How to get to it (user POV)

- Settings, Devices & services, Add integration, search `RET & NS Departures`, choose `ret`.
- The stop ID is the last path segment of the stop's page on ret.nl, such as `beurs`.

## Driving it with ha_verify.py

Preconditions:

- Doctor exits `0`.
- No entry titled `RET Beurs` exists.
- Entity IDs below assume the stop name `Beurs`. They are `<domain>.ret_<slug of stop name>_<suffix>`.

- **Open flow.** Start adding the integration. Run `V api --run <run-id> --label ret-add-form POST /api/config/config_entries/flow '{"handler":"ret_ns_departures"}'`. The response has `step_id` `user` and one field `operator` with options `ret` and `ns`.
- **Choose RET.** Run `V api --run <run-id> --label ret-add-operator POST /api/config/config_entries/flow/<flow_id> '{"operator":"ret"}'`. The response has `step_id` `ret` with fields `stop_id`, `stop_name`, and optional `line_filter`.
- **Invalid slug.** Run `V api --run <run-id> --label ret-add-invalid POST /api/config/config_entries/flow/<flow_id> '{"stop_id":"geen-echte-halte-xyz","stop_name":"Nope"}'`. The response stays `type` `form` with `errors` equal to `{"stop_id":"invalid_stop"}`.
- **Path-style ID.** Run `V api --run <run-id> --label ret-add-traversal POST /api/config/config_entries/flow/<flow_id> '{"stop_id":"../../home/contact","stop_name":"X"}'`. The response stays `type` `form` with `errors` equal to `{"stop_id":"invalid_stop"}`.
- **Create entry.** Run `V api --run <run-id> --label ret-add-create POST /api/config/config_entries/flow/<flow_id> '{"stop_id":"beurs","stop_name":"Beurs"}'`. The response has `type` `create_entry`, `title` `RET Beurs`, and `result.state` `loaded`.
- **Read entities.** Run `V api --run <run-id> --label ret-add-entities GET /api/states`. The response contains `sensor.ret_beurs_next_departure` whose state is an ISO timestamp, `sensor.ret_beurs_time_to_next_departure` whose state is a whole number of minutes, and `binary_sensor.ret_beurs_disruptions`.
- **Check attributes.** In the same response, the `sensor.ret_beurs_next_departure` attributes include `stop_name` `Beurs` and a `departures` list of up to 5 items with `line`, `destination`, and `scheduled_time`. While the list is not empty they also include `operator` `RET` and the next departure's own `line` and `destination`.
- **Duplicate.** Repeat Open flow and Choose RET, then submit `beurs` again with label `ret-add-duplicate`. The response has `type` `abort` and `reason` `already_configured`.
- **Line filter.** Remove `RET Beurs` per [Remove an entry](./remove-entry.md). On a fresh flow, submit `{"stop_id":"beurs","stop_name":"Beurs","line_filter":"1, 7"}` with label `ret-add-filter`. A following `GET /api/states` shows every item in the new sensor's `departures` with `line` `1` or `7`.

## Gotchas

- A stop that turns `unavailable` with `layout may have changed` in the log means ret.nl changed its halt page. That is a real finding, not a harness fault.
- Choose filter lines from a states capture taken moments earlier. A filter that matches nothing leaves both sensors at state `unknown` with an empty `departures` list, no `operator` attribute, and the plain name `RET Beurs Next departure`. The name reads `No service` only when RET also publishes a diversion notice for the stop.
- The `friendly_name` follows the next service, such as `RET Beurs Line 1 to Holy`. The entity ID does not. An entity ID that contains a line or destination is a regression.
- Late at night a stop can have no departures. An empty board is live data, not a failure. Pick a busy stop or report the empty state.
- The slug `centraal-station` resolves to `rotterdam-centraal`. The stored `stop_id` is the resolved slug.
- An invalid slug returns HTTP 200. Assert on `errors`.
- The helper prints exit code `0` for a form error because the HTTP status is 200.
