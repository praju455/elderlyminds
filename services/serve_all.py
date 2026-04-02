from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    module: str
    port_env: str
    default_port: int
    host: str


SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("ai", "services.ai_service.main:app", "AI_SERVICE_PORT", 8001, "127.0.0.1"),
    ServiceSpec("data", "services.data_service.main:app", "DATA_SERVICE_PORT", 8002, "127.0.0.1"),
    ServiceSpec("alerts", "services.alerts_service.main:app", "ALERTS_SERVICE_PORT", 8003, "127.0.0.1"),
    ServiceSpec("scheduler", "services.scheduler_service.main:app", "SCHEDULER_SERVICE_PORT", 8004, "127.0.0.1"),
    ServiceSpec("gateway", "gateway.main:app", "GATEWAY_PORT", 8010, "0.0.0.0"),
)


def _port_for(service: ServiceSpec) -> int:
    if service.name == "gateway":
        raw = os.getenv("PORT") or os.getenv(service.port_env) or str(service.default_port)
    else:
        raw = os.getenv(service.port_env) or str(service.default_port)
    return int(raw)


def _child_env(service: ServiceSpec) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env[service.port_env] = str(_port_for(service))
    if not env.get("MONGO_URI", "").strip():
        env["DATA_STORE_MODE"] = "local"
    if service.name == "gateway":
        env["GATEWAY_PORT"] = str(_port_for(service))
    return env


def _start(service: ServiceSpec) -> subprocess.Popen[bytes]:
    port = _port_for(service)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        service.module,
        "--host",
        service.host,
        "--port",
        str(port),
    ]
    print(f"[serve-all] starting {service.name} on http://{service.host}:{port}")
    if service.name == "data" and not os.getenv("MONGO_URI", "").strip():
        print("[serve-all] MONGO_URI not set, using local file store for data service")
    return subprocess.Popen(cmd, env=_child_env(service))


def _terminate(processes: list[tuple[ServiceSpec, subprocess.Popen[bytes]]]) -> None:
    for service, process in processes:
        if process.poll() is None:
            print(f"[serve-all] stopping {service.name}")
            process.terminate()

    deadline = time.time() + 10
    for _, process in processes:
        if process.poll() is not None:
            continue
        remaining = max(0.0, deadline - time.time())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    processes: list[tuple[ServiceSpec, subprocess.Popen[bytes]]] = []
    stopping = False

    def _handle_signal(signum: int, _frame) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        print(f"[serve-all] received signal {signum}, shutting down")
        _terminate(processes)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        for service in SERVICES:
            process = _start(service)
            processes.append((service, process))

        while True:
            for service, process in processes:
                code = process.poll()
                if code is None:
                    continue
                if stopping:
                    return 0
                print(f"[serve-all] {service.name} exited with code {code}")
                stopping = True
                _terminate(processes)
                return code or 1
            time.sleep(1)
    finally:
        _terminate(processes)


if __name__ == "__main__":
    raise SystemExit(main())
