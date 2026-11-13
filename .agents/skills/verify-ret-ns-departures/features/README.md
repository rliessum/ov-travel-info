# RET & NS Departures verification map

This directory is the maintained source for verifying the user-facing behavior of the RET & NS Departures integration. Read this index before driving, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch with `V launch --run <run-id>` as described in the skill.
- `V doctor --run <run-id>` exits `0`.
- A fresh instance has no `ret_ns_departures` entries.
- NS recipes need `ReisinformatiePrimaryKey` in the repo's `.env`.
- The machine can reach `www.ret.nl` and `gateway.apiportal.ns.nl`.
- Never drive an instance that this verification run did not start.

## Driving conventions

- `V` is the function defined in the skill. Every recipe passes `--run <run-id>`.
- Treat every JSON body as literal. Keep field names unchanged.
- `<flow_id>` and `<entry_id>` come from the previous response. Do not reuse one across runs.
- Entity IDs are `<domain>.<operator>_<slug of the name you entered>_<suffix>`, such as `sensor.ret_beurs_next_departure`. Live text appears only in `friendly_name`.
- Read states straight after an add. A `create_entry` response with `result.state` `loaded` means the first refresh already ran.
- Wait about 8 seconds after an options save before reading states. The entry reloads in the background.
- Pass the NS key as `"@env:ReisinformatiePrimaryKey"`, never as a literal.

## Proof and skip reporting

- Each `V api` call saves its own evidence file. Give every call a distinct `--label`.
- Proof of a new entry is the `create_entry` response plus a later `GET /api/states` showing its entities.
- Proof of a mutation includes a second read of the stored value.
- Record the feature ID with each label, such as `ret-add-create`.
- Report an unreachable path with the attempted command and the unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with ha_verify.py` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Add a RET stop](./add-ret-stop.md) covers the RET config flow, the invalid-stop error, duplicates, and the departure entities.
- [Add an NS station](./add-ns-station.md) covers API key entry, station lookup, station selection, and the departure, disruption, and image entities.
- [Configure an entry](./configure-entry.md) covers max departures, the RET line filter, and the NS disruption toggle.
- [Remove an entry](./remove-entry.md) covers deleting an entry and its entities.
- [Download diagnostics](./download-diagnostics.md) covers the diagnostics file for an entry and its redaction.
