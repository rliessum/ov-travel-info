# Add an NS station

A user enters an NS API key, searches for a station by name or map location, picks one from the results, and gets train departure sensors, an optional disruption binary sensor, and a next-train image for that station.

## Sub-features

- `ns-add-form` shows the key, location, and station query fields.
- `ns-add-lookup` returns matching stations as a dropdown.
- `ns-add-bad-key` rejects a wrong API key.
- `ns-add-no-key` rejects a blank API key with a field error.
- `ns-add-no-match` reports a query that matches no station.
- `ns-add-create` creates the entry `NS <station name>`.
- `ns-add-entities` exposes departure sensors, the disruption sensor, and the image.
- `ns-add-image-stable` keeps the image timestamp while the next train is unchanged.
- `ns-add-second` lets a second station reuse the stored key.
- `ns-add-duplicate` refuses the same station twice.

## How to get to it (user POV)

- Settings, Devices & services, Add integration, search `RET & NS Departures`, choose `ns`.
- Enter the API key, optionally move the map pin, optionally type a station name, then pick a station.

## Driving it with ha_verify.py

Preconditions:

- Doctor exits `0`.
- `.env` holds `ReisinformatiePrimaryKey`.
- No entry titled `NS Rotterdam Centraal` exists.

- **Open flow.** Run `V api --run <run-id> --label ns-add-form POST /api/config/config_entries/flow '{"handler":"ret_ns_departures"}'`, then `V api --run <run-id> --label ns-add-operator POST /api/config/config_entries/flow/<flow_id> '{"operator":"ns"}'`. The first response has `step_id` `user`. The second has `step_id` `ns` with required `ns_api_key`, a `location` field defaulting to the instance's home location, and optional `station_query`. The helper sets home to latitude `51.9225` and longitude `4.47917`.
- **Look up station.** Run `V api --run <run-id> --label ns-add-lookup POST /api/config/config_entries/flow/<flow_id> '{"ns_api_key":"@env:ReisinformatiePrimaryKey","location":{"latitude":51.9225,"longitude":4.47917},"station_query":"Rotterdam Centraal"}'`. The response has `step_id` `ns_select`, and the `station` options include value `RTD` with a label starting `Rotterdam Centraal (RTD)`, followed by the distance from the submitted location. `monitor_disruptions` defaults to `true`.
- **Create entry.** Run `V api --run <run-id> --label ns-add-create POST /api/config/config_entries/flow/<flow_id> '{"station":"RTD","monitor_disruptions":true}'`. The response has `type` `create_entry` and `title` `NS Rotterdam Centraal`.
- **Read entities.** Run `V api --run <run-id> --label ns-add-entities GET /api/states`. The response contains `sensor.ns_rotterdam_centraal_next_departure` with an ISO timestamp state, `sensor.ns_rotterdam_centraal_time_to_next_departure`, `binary_sensor.ns_rotterdam_centraal_disruptions`, and `image.ns_rotterdam_centraal_next_train`.
- **Image is not refetched.** Read `GET /api/states/image.ns_rotterdam_centraal_next_train` and `GET /api/states/sensor.ns_rotterdam_centraal_next_departure` as a baseline. Wait 70 seconds and read both again with label `ns-add-image-stable`. The image state timestamp is unchanged while the sensor still names the same train in `friendly_name`.
- **Check disruption attributes.** In the Read entities response, the binary sensor has `station_name` and `count`. When its state is `on` it also has `disruptions`, `title`, and `message`.
- **Bad key.** On a fresh instance with no NS entry, submit the lookup step with `"ns_api_key":"not-a-real-key"` and label `ns-add-bad-key`. The response stays `type` `form` with `errors` equal to `{"base":"invalid_auth"}`.
- **Blank key.** On the same fresh instance, submit the lookup step with `"ns_api_key":" "` and label `ns-add-no-key`. The response stays `type` `form` with `errors` equal to `{"ns_api_key":"api_key_required"}`.
- **No match.** Submit the lookup step with the real key and `"station_query":"zzzzqqqxxx"` with label `ns-add-no-match`. The response stays `type` `form` with `errors` equal to `{"base":"no_stations_found"}`.
- **Second station.** With one NS entry present, open a new flow and choose `ns`. The `ns_api_key` field is now optional. Submit `{"location":{"latitude":52.0894,"longitude":5.1100},"station_query":"Utrecht Centraal"}` with label `ns-add-second`. The response reaches `ns_select` without a key in the request.
- **Duplicate.** With `NS Rotterdam Centraal` present, open a new flow, choose `ns`, look up `Rotterdam Centraal` without a key, and submit `{"station":"RTD","monitor_disruptions":true}` with label `ns-add-duplicate`. The response has `type` `abort` and `reason` `already_configured`.

## Gotchas

- The key appears as `<redacted>` in evidence. Confirm that before sharing an evidence directory.
- The `friendly_name` of the departure and disruption sensors carries live text, such as a train number or a disruption title. The entity IDs do not. An ID that contains live text is a regression.
- The image is fetched again every 10 minutes for the same train. Its timestamp moves only when the picture itself changed.
- The image timestamp also moves when the next train changes. Take the baseline just after a departure, so the same train stays next for the 70 seconds. A changed `friendly_name` on the sensor voids the comparison, not the feature.
- A disruption sensor that reads `unknown` means NS has not answered the disruptions request for 30 minutes. It is not a regression.
- The reauth step for a rejected key has no recipe. It cannot be reached through this harness without a revoked key. Unit tests cover it.
- The disruption sensor is `on` only while NS reports an active disruption. Either state is valid. Prove the feature by the presence of the entity and its attributes.
- A bad key and a query with no matches both keep the form open. Tell them apart by `errors.base`, which is `invalid_auth` or `no_stations_found`. A blank key is a field error on `ns_api_key`, not on `base`.
- Run the bad-key and blank-key checks before any NS entry exists, so the result cannot depend on a stored key.
- Abandon a flow you stop at `ns_select` with `DELETE /api/config/config_entries/flow/<flow_id>`.
- The image entity's attributes contain an `access_token` for the image proxy. It is local to the disposable instance.
