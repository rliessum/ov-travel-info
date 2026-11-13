---
name: verify-ret-ns-departures
description: Drive the RET & NS Departures Home Assistant integration in a real, disposable Home Assistant instance and capture proof. Use to verify a change to the config flow, options, sensors, disruption binary sensors, or the NS train image against live ret.nl and NS data, beyond what pytest shows.
---

# Verify RET & NS Departures

The surface a user touches is Home Assistant. They add the integration under Settings, Devices & services, then read entities. This skill starts a throwaway Home Assistant with this checkout's `custom_components/ret_ns_departures` linked in, drives it through the same REST endpoints the Home Assistant frontend calls, and saves every request and response as evidence.

The instance runs headless. The `.venv` has Home Assistant core but not the `home-assistant-frontend` package, so there is no browser UI to open. Do not report a browser check as done.

All commands run from the repo root. `V` below stands for the helper.

```bash
V() { .venv/bin/python .agents/skills/verify-ret-ns-departures/scripts/ha_verify.py "$@"; }
```

Define it as a function. In zsh a plain variable holding the command does not word-split and fails with exit 127.

## Launch

```bash
V launch --run <run-id>
```

`<run-id>` is any short label you choose, such as `ret-fix-1`. Omit `--run` to get a timestamp. The command returns once Home Assistant reports state `RUNNING`, usually within 15 seconds, and prints the port, config directory, and evidence directory as JSON.

Launch does the following, so you do not:

- Creates a scratch config directory at `$TMPDIR/ret-ns-verify/<run-id>` with a symlink to this checkout's integration.
- Picks a free port and binds `127.0.0.1` only.
- Onboards a local user and stores an access token in the scratch directory.

If `.venv` is missing, create it first with `uv venv .venv && uv pip install -r requirements_test.txt`.

Edits to the integration's Python files need a restart to load. Run cleanup, then launch again with a new run id.

## Doctor

```bash
V doctor --run <run-id>
```

Read-only. Exit code `0` and `"healthy": true` mean the instance is worth driving. It checks that the process is the one launch started, that the linked integration is this checkout, that the API answers with the token, and that Home Assistant state is `RUNNING`. It also prints the manifest version and the integration's config entries with their load state. `integration_loaded` stays `false` until the first config entry exists. That is expected.

Run doctor first whenever a call fails or times out.

## Drive

```bash
V api --run <run-id> --label <label> <METHOD> <path> ['<json body>']
```

Each call prints `status`, the parsed `response`, and the evidence file it saved. Exit code is `1` for HTTP status 400 and above.

Endpoints the feature recipes use:

- `POST /api/config/config_entries/flow` with `{"handler":"ret_ns_departures"}` starts the add-integration flow. The response carries `flow_id` and `step_id`.
- `POST /api/config/config_entries/flow/<flow_id>` submits the current step's form.
- `GET /api/config/config_entries/entry?domain=ret_ns_departures` lists entries with `entry_id`, `title`, and `state`.
- `POST /api/config/config_entries/options/flow` with `{"handler":"<entry_id>"}` opens Configure for an entry. Submit to `/api/config/config_entries/options/flow/<flow_id>`.
- `DELETE /api/config/config_entries/entry/<entry_id>` removes an entry.
- `DELETE /api/config/config_entries/flow/<flow_id>` abandons an unfinished flow, as closing the dialog does in the UI. Abandon every flow you do not finish. An open flow keeps its stop reserved and blocks a later add of the same stop.
- `GET /api/states` returns every entity. `GET /api/states/<entity_id>` returns one.

A form error comes back as HTTP 200 with `"type": "form"` and a non-empty `errors` object. Assert on `type` and `errors`, not on the status code.

Secrets. Never put the NS API key on a command line. Write the string `"@env:ReisinformatiePrimaryKey"` as the JSON value. The helper reads it from `.env` and redacts it from saved evidence and printed output.

Per-feature recipes live in [`features/`](features/README.md). Read the index before driving.

## Evidence

Evidence lands in `.verify/<run-id>/` at the repo root. The directory is gitignored.

- `NN-<label>.json` holds one request and its response, numbered in call order.
- `run.json` holds the port and paths, without the token.
- `home-assistant.log` and `hass-stdout.log` are copied in by cleanup. The integration logs at debug level.

Proof standards for this repo:

- Go through the config flow. Do not write `.storage/core.config_entries` by hand.
- Capture the action and the resulting state. A `create_entry` response alone is not proof. Follow it with a `GET /api/states` that shows the entities and their values.
- Data is live from ret.nl and the NS API. Assert shape and plausibility (a timestamp in the near future, a `departures` list, the configured `stop_name`), not fixed destinations or times.
- After a removal, capture states again and show the entities are gone.
- Scan `home-assistant.log` in the evidence directory for `ERROR` and `Traceback` after cleanup, and report what you find.

## Cleanup

```bash
V cleanup --run <run-id>
```

Stops only the process that launch started for that run, copies the logs into the evidence directory, and deletes the scratch config directory. `.verify/<run-id>/` survives. Run cleanup after a failed attempt too, so no instance or port is stranded.

Never stop Home Assistant by process name. The user may run a real instance on this machine.

## Isolation

Runs are independent. Each has its own port, config directory, and token, so two runs can drive side by side. Both share live upstream services, so keep the number of parallel runs small.

## Helpers

`scripts/ha_verify.py` is the only helper. It uses the standard library only. `V --help` and `V <command> --help` list every flag.
