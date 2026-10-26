"""BuddyCheck sensor backends: Android hardware and explicitly generated test data."""

import json
from math import isfinite, sin, pi
from random import Random
from shutil import which
from subprocess import CalledProcessError, TimeoutExpired, run
from time import monotonic
from typing import Protocol

from shared.processing import GRAVITY, SensorSample


class SensorSource(Protocol):
    def read(self) -> SensorSample: ...


def _api(*arguments: str):
    try:
        response = run(
            ["termux-sensor", *arguments], capture_output=True, text=True,
            encoding="utf-8", timeout=12, check=True,
        )
        return json.loads(response.stdout)
    except (CalledProcessError, TimeoutExpired, OSError, ValueError) as error:
        raise RuntimeError("Termux:API gagal. Periksa instalasi, izin, dan keluaran termux-sensor -l.") from error


def _axes(record: object) -> tuple[float, float, float]:
    values = record.get("values") if isinstance(record, dict) else None
    if not isinstance(values, list) or len(values) < 3:
        raise RuntimeError("Pembacaan sensor tidak memiliki tiga sumbu")
    selected = values[:3]
    if any(type(value) not in (int, float) or not isfinite(value) for value in selected):
        raise RuntimeError("Pembacaan sensor mengandung angka tidak valid")
    return tuple(map(float, selected))


class TermuxSensors:
    """Read gravity-inclusive acceleration and calibrated angular velocity."""

    def __init__(self):
        if which("termux-sensor") is None:
            raise RuntimeError("Pasang aplikasi Termux:API dan paket termux-api terlebih dahulu")
        inventory = _api("-l")
        names = inventory.get("sensors") if isinstance(inventory, dict) else inventory
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise RuntimeError("Daftar sensor Android tidak dikenali")
        self.channels = {}
        for name in names:
            normalized = name.casefold()
            if "uncalibrated" in normalized or "linear" in normalized:
                continue
            if "accelerometer" in normalized or "acceleration sensor" in normalized:
                self.channels.setdefault("acceleration", name)
            if "gyroscope" in normalized:
                self.channels.setdefault("gyroscope", name)
        missing = {"acceleration", "gyroscope"} - self.channels.keys()
        if missing:
            raise RuntimeError("Sensor wajib belum tersedia: " + ", ".join(sorted(missing)))
        for kind, name in self.channels.items():
            print(f"[BuddyCheck sensor] {kind}: {name}", flush=True)

    def read(self) -> SensorSample:
        response = _api("-s", ",".join(self.channels.values()), "-n", "1", "-d", "100")
        if not isinstance(response, dict):
            raise RuntimeError("Respons sensor Android bukan objek")
        return SensorSample(
            seconds=monotonic(),
            acceleration=_axes(response.get(self.channels["acceleration"])),
            gyroscope=_axes(response.get(self.channels["gyroscope"])),
        )


class GeneratedMotion:
    """Repeatable software-test input. This backend never represents a real phone."""

    def __init__(self, scenario: str):
        if scenario not in ("still", "incident"):
            raise ValueError("Skenario simulasi harus still atau incident")
        self.scenario = scenario
        self.origin = monotonic()
        self.noise = Random(218)

    def read(self) -> SensorSample:
        timestamp = monotonic()
        phase = timestamp - self.origin
        pulse = sin(pi * (phase - 3)) if self.scenario == "incident" and 3 < phase < 4 else 0
        jitter = [self.noise.uniform(-0.025, 0.025) for _ in range(6)]
        return SensorSample(
            seconds=timestamp,
            acceleration=(jitter[0], jitter[1], GRAVITY + 18 * pulse + jitter[2]),
            gyroscope=(2.0 * pulse + jitter[3], jitter[4], jitter[5]),
        )


def select_source(name: str, scenario: str) -> SensorSource:
    factories = {"android": TermuxSensors, "simulator": lambda: GeneratedMotion(scenario)}
    if name not in factories:
        raise ValueError("Sumber sensor tidak dikenal: " + name)
    return factories[name]()
