# Remove an entry

A user deletes a stop or station from the integration, and its entities disappear from Home Assistant without a restart.

## Sub-features

- `remove-entry` deletes the entry without requiring a restart.
- `remove-entities` leaves no entities for the removed stop.
- `remove-readd` allows the same stop to be added again.
- `remove-last-ns` makes the next NS flow ask for the API key again.

## How to get to it (user POV)

- Settings, Devices & services, RET & NS Departures, the entry's menu, then Delete.

## Driving it with ha_verify.py

Preconditions:

- Doctor exits `0`.
- The entry `RET Beurs` exists and `GET /api/states` shows `sensor.ret_beurs_*` entities.

- **Find entry.** Run `V api --run <run-id> --label remove-entries GET "/api/config/config_entries/entry?domain=ret_ns_departures"`. Take `entry_id` from the item whose `title` is `RET Beurs`.
- **Delete.** Run `V api --run <run-id> --label remove-entry DELETE /api/config/config_entries/entry/<entry_id>`. The response is `{"require_restart": false}`.
- **Confirm entities gone.** Run `V api --run <run-id> --label remove-entities GET /api/states`. No entity ID contains `ret_beurs`.
- **Confirm entry gone.** Repeat Find entry with label `remove-entries-after`. No item is titled `RET Beurs`.
- **Add again.** Run the Open flow, Choose RET, and Create entry steps from [Add a RET stop](./add-ret-stop.md) with label `remove-readd`. The response has `type` `create_entry`, not `abort`.
- **Remove the last NS entry.** With `NS Rotterdam Centraal` as the only NS entry, delete it with label `remove-last-ns`. Open a new flow and choose `ns` with label `remove-last-ns-form`. The `ns_api_key` field is `required` again. Abandon that flow.

## Gotchas

- The API key is kept with each NS entry and offered from any NS entry that remains. Removing the last one drops it.
- Other entries must stay `loaded`. Check their `state` in the Confirm entry gone response.
- An `entry_id` is dead after deletion. A second `DELETE` returns HTTP 404 and the helper exits `1`.
