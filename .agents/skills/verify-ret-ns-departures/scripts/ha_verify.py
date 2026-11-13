#!/usr/bin/env python3
"""Launch, check, drive, and tear down a disposable Home Assistant for this repo."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DOMAIN = "ret_ns_departures"
COMPONENT = REPO / "custom_components" / DOMAIN
EVIDENCE_ROOT = REPO / ".verify"
SCRATCH_ROOT = Path(tempfile.gettempdir()) / "ret-ns-verify"
HOST = "127.0.0.1"
CLIENT_ID = f"http://{HOST}/"
READY_TIMEOUT_S = 180
REDACTED = "<redacted>"

CONFIGURATION = """\
homeassistant:
  name: RET NS verify
  latitude: 51.9225
  longitude: 4.47917
  time_zone: Europe/Amsterdam
  unit_system: metric
  country: NL
http:
  server_host: {host}
  server_port: {port}
api:
config:
onboarding:
logger:
  default: warning
  logs:
    custom_components.{domain}: debug
"""


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def scratch_dir(run: str) -> Path:
    return SCRATCH_ROOT / run


def evidence_dir(run: str) -> Path:
    return EVIDENCE_ROOT / run


def load_state(run: str) -> dict:
    path = scratch_dir(run) / "verify-run.json"
    if not path.exists():
        fail(f"no instance for run '{run}' (expected {path}). Run launch first.")
    return json.loads(path.read_text())


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    path = REPO / ".env"
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("\"'")
    return values


def substitute_env(node, secrets: list[str]):
    """Replace "@env:NAME" strings with the value from .env, recording each secret."""
    if isinstance(node, dict):
        return {key: substitute_env(value, secrets) for key, value in node.items()}
    if isinstance(node, list):
        return [substitute_env(value, secrets) for value in node]
    if isinstance(node, str) and node.startswith("@env:"):
        name = node[len("@env:"):]
        value = read_env_file().get(name) or os.environ.get(name)
        if not value:
            fail(f"{name} is not set in {REPO / '.env'} or the environment")
        secrets.append(value)
        return value
    return node


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    return text


def http(method: str, url: str, body=None, token: str | None = None, form: bool = False):
    headers = {}
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def parse(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


def pid_command(pid: int) -> str:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def owns_pid(state: dict) -> bool:
    return state["config_dir"] in pid_command(state["pid"])


def cmd_launch(args: argparse.Namespace) -> None:
    run = args.run or time.strftime("%Y%m%d-%H%M%S")
    config = scratch_dir(run)
    if config.exists():
        fail(f"run '{run}' already exists at {config}. Clean it up or pick another --run.")
    python = REPO / ".venv" / "bin" / "python"
    if not python.exists():
        fail(f"{python} missing. Create it: uv venv .venv && uv pip install -r requirements_test.txt")

    port = args.port or free_port()
    (config / "custom_components").mkdir(parents=True)
    (config / "custom_components" / DOMAIN).symlink_to(COMPONENT, target_is_directory=True)
    (config / "configuration.yaml").write_text(
        CONFIGURATION.format(host=HOST, port=port, domain=DOMAIN)
    )
    evidence = evidence_dir(run)
    evidence.mkdir(parents=True, exist_ok=True)

    log = open(config / "hass-stdout.log", "w")
    process = subprocess.Popen(
        [str(python), "-m", "homeassistant", "-c", str(config)],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=config,
    )
    base = f"http://{HOST}:{port}"
    state = {
        "run": run,
        "pid": process.pid,
        "port": port,
        "base_url": base,
        "config_dir": str(config),
        "evidence_dir": str(evidence),
        "token": None,
    }
    state_path = config / "verify-run.json"
    state_path.write_text(json.dumps(state, indent=2))

    deadline = time.time() + READY_TIMEOUT_S
    while True:
        if process.poll() is not None:
            fail(f"Home Assistant exited with {process.returncode}. See {config / 'hass-stdout.log'}")
        try:
            status, _ = http("GET", f"{base}/api/onboarding")
            if status == 200:
                break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        if time.time() > deadline:
            fail(f"not ready after {READY_TIMEOUT_S}s. See {config / 'hass-stdout.log'}, then run cleanup.")
        time.sleep(1)

    status, text = http(
        "POST",
        f"{base}/api/onboarding/users",
        {
            "client_id": CLIENT_ID,
            "name": "Verify",
            "username": "verify",
            "password": "verify-only-local",
            "language": "en",
        },
    )
    if status != 200:
        fail(f"onboarding failed with {status}: {text}")
    status, text = http(
        "POST",
        f"{base}/auth/token",
        {"client_id": CLIENT_ID, "grant_type": "authorization_code", "code": json.loads(text)["auth_code"]},
        form=True,
    )
    if status != 200:
        fail(f"token exchange failed with {status}: {text}")
    state["token"] = json.loads(text)["access_token"]
    state_path.write_text(json.dumps(state, indent=2))

    while True:
        status, text = http("GET", f"{base}/api/config", token=state["token"])
        if status == 200 and json.loads(text).get("state") == "RUNNING":
            break
        if time.time() > deadline:
            fail(f"started but never reached RUNNING. See {config / 'hass-stdout.log'}, then run cleanup.")
        time.sleep(1)

    public = {key: value for key, value in state.items() if key != "token"}
    (evidence / "run.json").write_text(json.dumps(public, indent=2))
    print(json.dumps(public, indent=2))


def cmd_doctor(args: argparse.Namespace) -> None:
    state = load_state(args.run)
    checks: dict[str, object] = {}
    checks["pid_is_ours"] = owns_pid(state)
    link = Path(state["config_dir"]) / "custom_components" / DOMAIN
    checks["component_is_this_checkout"] = link.resolve() == COMPONENT.resolve()
    checks["manifest_version"] = json.loads((COMPONENT / "manifest.json").read_text())["version"]
    try:
        status, text = http("GET", f"{state['base_url']}/api/config", token=state["token"])
        config = parse(text) if status == 200 else {}
        checks["api_status"] = status
        checks["ha_version"] = config.get("version")
        checks["ha_state"] = config.get("state")
        checks["integration_loaded"] = DOMAIN in config.get("components", [])
        status, text = http(
            "GET",
            f"{state['base_url']}/api/config/config_entries/entry?domain={DOMAIN}",
            token=state["token"],
        )
        entries = parse(text) if status == 200 else []
        checks["entries"] = [f"{entry['title']} ({entry['state']})" for entry in entries]
    except (urllib.error.URLError, ConnectionError, TimeoutError) as err:
        checks["api_status"] = f"unreachable: {err}"
    healthy = (
        checks["pid_is_ours"]
        and checks["component_is_this_checkout"]
        and checks.get("api_status") == 200
        and checks.get("ha_state") == "RUNNING"
    )
    checks["healthy"] = bool(healthy)
    print(json.dumps(checks, indent=2))
    sys.exit(0 if healthy else 1)


def cmd_api(args: argparse.Namespace) -> None:
    state = load_state(args.run)
    secrets: list[str] = [state["token"]]
    body = substitute_env(json.loads(args.body), secrets) if args.body else None
    status, text = http(args.method.upper(), state["base_url"] + args.path, body, token=state["token"])
    response = parse(redact(text, secrets))
    record = {
        "request": {
            "method": args.method.upper(),
            "path": args.path,
            "body": parse(redact(json.dumps(body), secrets)) if body is not None else None,
        },
        "status": status,
        "response": response,
    }
    evidence = Path(state["evidence_dir"])
    index = len(list(evidence.glob("[0-9][0-9]-*.json"))) + 1
    out = evidence / f"{index:02d}-{args.label}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(json.dumps({"status": status, "saved": str(out), "response": response}, indent=2, ensure_ascii=False))
    sys.exit(0 if status < 400 else 1)


def cmd_cleanup(args: argparse.Namespace) -> None:
    state = load_state(args.run)
    config = Path(state["config_dir"])
    evidence = Path(state["evidence_dir"])
    pid = state["pid"]
    if owns_pid(state):
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not pid_command(pid):
                break
            time.sleep(1)
        else:
            os.kill(pid, signal.SIGKILL)
    secrets = [value for value in [state["token"], *read_env_file().values()] if value]
    for name in ("home-assistant.log", "hass-stdout.log"):
        source = config / name
        if source.exists():
            (evidence / name).write_text(redact(source.read_text(errors="replace"), secrets))
    shutil.rmtree(config)
    print(json.dumps({"stopped_pid": pid, "removed": str(config), "evidence": str(evidence)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    launch = sub.add_parser("launch", help="start a disposable Home Assistant and onboard it")
    launch.add_argument("--run", help="run id (default: timestamp)")
    launch.add_argument("--port", type=int, help="port (default: a free one)")
    launch.set_defaults(func=cmd_launch)

    doctor = sub.add_parser("doctor", help="read-only health check, exit 0 when worth driving")
    doctor.add_argument("--run", required=True)
    doctor.set_defaults(func=cmd_doctor)

    api = sub.add_parser("api", help="authenticated REST call, saved as numbered evidence")
    api.add_argument("--run", required=True)
    api.add_argument("--label", required=True, help="evidence file label, e.g. ret-flow-start")
    api.add_argument("method")
    api.add_argument("path", help="path with query, e.g. /api/states")
    api.add_argument("body", nargs="?", help='JSON body; a string value "@env:NAME" is read from .env')
    api.set_defaults(func=cmd_api)

    cleanup = sub.add_parser("cleanup", help="stop the instance, keep logs and evidence, drop scratch")
    cleanup.add_argument("--run", required=True)
    cleanup.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
