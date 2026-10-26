"""Validated MQTT contracts, independent of networking and sensor hardware."""

from dataclasses import asdict, dataclass
import json
import math

DEVICES = ("edge1", "edge2")


def json_object(payload: str | bytes) -> dict:
    if len(payload) > 16_384:
        raise ValueError("Payload terlalu besar")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Payload harus berupa objek JSON")
    return value


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise ValueError(f"{name} tidak valid")
    if not all(char.isascii() and (char.isalnum() or char in "_-") for char in value):
        raise ValueError(f"{name} hanya boleh huruf, angka, - dan _")
    return value


def integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} tidak valid")
    return value


def number(value: object, name: str, maximum: float = 10000) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{name} tidak valid")
    return float(value)


@dataclass(frozen=True)
class Telemetry:
    device_id: str
    boot_id: str
    sequence: int
    sent_at_ms: int
    motion_rms: float
    rotation_rad: float
    accel_peak: float
    window_ms: int
    sample_count: int
    source: str = "physical"

    def to_json(self) -> str:
        return json.dumps(asdict(self), allow_nan=False)

    @classmethod
    def from_json(cls, payload: str | bytes) -> "Telemetry":
        data = json_object(payload)
        if data.get("device_id") not in DEVICES:
            raise ValueError("Device harus edge1 atau edge2")
        if data.get("source") not in ("physical", "simulator"):
            raise ValueError("Source harus physical atau simulator")
        return cls(
            device_id=data["device_id"], boot_id=identifier(data.get("boot_id"), "boot_id"),
            sequence=integer(data.get("sequence"), "sequence", 0, 2**53 - 1),
            sent_at_ms=integer(data.get("sent_at_ms"), "sent_at_ms", 0, 2**53 - 1),
            motion_rms=number(data.get("motion_rms"), "motion_rms"),
            rotation_rad=number(data.get("rotation_rad"), "rotation_rad"),
            accel_peak=number(data.get("accel_peak"), "accel_peak"),
            window_ms=integer(data.get("window_ms"), "window_ms", 100, 3000),
            sample_count=integer(data.get("sample_count"), "sample_count", 4, 1000),
            source=data["source"],
        )


@dataclass(frozen=True)
class Command:
    command_id: str
    action: str
    actor: str
    event_id: str
    sent_at_ms: int

    @classmethod
    def from_json(cls, payload: str | bytes) -> "Command":
        data = json_object(payload)
        action = data.get("action")
        if action not in ("JOIN", "REQUEST_STATUS", "SAFE", "NEED_HELP", "ACKNOWLEDGE", "ARM", "DISARM"):
            raise ValueError("Action tidak dikenal")
        actor = data.get("actor")
        if actor not in (*DEVICES, "dashboard"):
            raise ValueError("Actor tidak dikenal")
        event_id = "" if action in ("JOIN", "ARM", "DISARM") else identifier(data.get("event_id"), "event_id")
        return cls(
            identifier(data.get("command_id"), "command_id"), action, actor, event_id,
            integer(data.get("sent_at_ms"), "sent_at_ms", 0, 2**53 - 1),
        )
