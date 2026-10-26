"""Temporal detection and two-way check-in state machine. No network dependencies."""

from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, field
import math
import os
import uuid

from shared.messages import Command, DEVICES, Telemetry


class SensorSessionConflict(ValueError):
    """A sender continues using a role that another sensor session replaced."""


@dataclass(frozen=True)
class Config:
    impact_peak: float = 8.0
    impact_rotation: float = 0.35
    still_rms: float = 0.6
    still_rotation: float = 0.15
    still_seconds: float = 5.0
    observation_seconds: float = 12.0
    offline_seconds: float = 8.0
    reply_seconds: float = 30.0
    check_seconds: float = 60.0
    cooldown_seconds: float = 15.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} harus angka positif")
        if self.observation_seconds <= self.still_seconds:
            raise ValueError("OBSERVATION_SECONDS harus lebih besar dari STILL_SECONDS")

    @classmethod
    def from_env(cls):
        return cls(**{key: float(os.getenv(key.upper(), default)) for key, default in asdict(cls()).items()})


@dataclass
class Device:
    telemetry: Telemetry | None = None
    last_seen_ms: int | None = None
    impact_at_ms: int | None = None
    still_since_ms: int | None = None
    cooldown_until_ms: int = 0
    retired_boots: deque = field(default_factory=lambda: deque(maxlen=16))


class BuddyCheck:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.armed = True
        self.devices = {name: Device() for name in DEVICES}
        self.events: OrderedDict[str, dict] = OrderedDict()
        self.active: dict[str, str] = {}
        self.commands: OrderedDict[str, None] = OrderedDict()
        self.revision = 0

    def _online(self, device: Device, now_ms: int) -> bool:
        return device.last_seen_ms is not None and now_ms - device.last_seen_ms < self.config.offline_seconds * 1000

    def accept(self, reading: Telemetry, now_ms: int) -> bool:
        if abs(now_ms - reading.sent_at_ms) > 15_000:
            raise ValueError("Telemetri kedaluwarsa; periksa jam HP")
        device = self.devices[reading.device_id]
        previous = device.telemetry
        if previous:
            if reading.boot_id == previous.boot_id:
                if reading.sequence <= previous.sequence or reading.sent_at_ms <= previous.sent_at_ms:
                    raise ValueError("Telemetri duplikat atau di luar urutan")
            elif reading.boot_id in device.retired_boots:
                label = "HP A" if reading.device_id == "edge1" else "HP B"
                raise SensorSessionConflict(
                    f"Sesi {label} digantikan sesi lain dalam ID kelompok yang sama. "
                    "Tutup tab sensor lain yang memakai peran ini; gunakan HP A di satu HP dan HP B di HP lainnya."
                )
            else:
                # A new browser/Termux session cannot inherit an old impact.
                device.retired_boots.append(previous.boot_id)
                device.impact_at_ms = device.still_since_ms = None
        if device.last_seen_ms is not None and now_ms - device.last_seen_ms > 3000:
            device.impact_at_ms = device.still_since_ms = None
        if previous and previous.source != reading.source:
            device.impact_at_ms = device.still_since_ms = None
        device.telemetry = reading
        device.last_seen_ms = now_ms
        self.revision += 1
        self.tick(now_ms)
        if not self.armed or reading.device_id in self.active or now_ms < device.cooldown_until_ms:
            return False
        config = self.config
        impact = reading.accel_peak >= config.impact_peak and reading.rotation_rad >= config.impact_rotation
        still = reading.motion_rms <= config.still_rms and reading.rotation_rad <= config.still_rotation
        if impact:
            device.impact_at_ms = now_ms
            device.still_since_ms = None
        elif device.impact_at_ms is not None:
            if now_ms - device.impact_at_ms > config.observation_seconds * 1000:
                device.impact_at_ms = device.still_since_ms = None
            elif still:
                if device.still_since_ms is None:
                    device.still_since_ms = now_ms
                if now_ms - device.still_since_ms >= config.still_seconds * 1000:
                    self._open_event(reading.device_id, now_ms)
                    return True
            else:
                device.still_since_ms = None
        return False

    def _open_event(self, subject: str, now_ms: int):
        event_id = uuid.uuid4().hex
        self.events[event_id] = {
            "event_id": event_id, "subject": subject,
            "buddy": "edge2" if subject == "edge1" else "edge1",
            "status": "CHECK_BUDDY", "created_at_ms": now_ms, "updated_at_ms": now_ms,
            "expires_at_ms": now_ms + int(self.config.check_seconds * 1000),
            "reason": "Lonjakan percepatan dan rotasi diikuti kondisi diam.",
            "source": self.devices[subject].telemetry.source,
        }
        self.active[subject] = event_id
        self.devices[subject].impact_at_ms = self.devices[subject].still_since_ms = None
        while len(self.events) > 50:
            oldest = next((key for key in self.events if key not in self.active.values()), None)
            if oldest is None:
                break
            del self.events[oldest]
        self.revision += 1

    def command(self, command: Command, now_ms: int) -> bool:
        self.tick(now_ms)
        if abs(now_ms - command.sent_at_ms) > 15_000:
            raise ValueError("Perintah kedaluwarsa")
        if command.command_id in self.commands:
            return False  # QoS 1 can deliver the same command twice.
        if command.action in ("ARM", "DISARM"):
            if command.actor != "dashboard":
                raise ValueError("Monitoring diatur dari dashboard")
            self.armed = command.action == "ARM"
            for device in self.devices.values():
                device.impact_at_ms = device.still_since_ms = None
        else:
            event = self.events.get(command.event_id)
            if event is None or command.event_id not in self.active.values():
                raise ValueError("Kejadian tidak aktif atau tidak ditemukan")
            action = command.action
            if action == "REQUEST_STATUS":
                if command.actor != event["buddy"] or event["status"] not in ("CHECK_BUDDY", "NO_RESPONSE"):
                    raise ValueError("Permintaan hanya dapat dikirim teman pada kejadian yang belum dijawab")
                event["status"] = "AWAITING_REPLY"
                event["expires_at_ms"] = now_ms + int(self.config.reply_seconds * 1000)
            elif action in ("SAFE", "NEED_HELP"):
                if command.actor != event["subject"] or event["status"] != "AWAITING_REPLY":
                    raise ValueError("Jawaban hanya dari pengguna yang ditanya saat permintaan aktif")
                event["status"] = action
                event["expires_at_ms"] = None
                if action == "SAFE":
                    self._close(event, now_ms)
            elif action == "ACKNOWLEDGE":
                if command.actor != event["buddy"] or event["status"] not in ("NEED_HELP", "NO_RESPONSE"):
                    raise ValueError("Teman hanya dapat menyelesaikan status perlu bantuan/tidak ada jawaban")
                event["status"] = "CLOSED"
                event["expires_at_ms"] = None
                self._close(event, now_ms)
            event["updated_at_ms"] = now_ms
        self.commands[command.command_id] = None
        if len(self.commands) > 512:
            self.commands.popitem(last=False)
        self.revision += 1
        return True

    def _close(self, event: dict, now_ms: int):
        self.active.pop(event["subject"], None)
        device = self.devices[event["subject"]]
        device.cooldown_until_ms = now_ms + int(self.config.cooldown_seconds * 1000)
        device.impact_at_ms = device.still_since_ms = None

    def tick(self, now_ms: int):
        for device in self.devices.values():
            if device.last_seen_ms is not None and now_ms - device.last_seen_ms > 3000:
                device.impact_at_ms = device.still_since_ms = None
        for event_id in list(self.active.values()):
            event = self.events[event_id]
            if event["expires_at_ms"] is not None and now_ms >= event["expires_at_ms"]:
                event["status"] = "NO_RESPONSE"
                event["updated_at_ms"] = now_ms
                event["expires_at_ms"] = None
                self.revision += 1

    def snapshot(self, now_ms: int) -> dict:
        self.tick(now_ms)
        devices = {}
        for name, device in self.devices.items():
            online = self._online(device, now_ms)
            status = "OFFLINE"
            if online:
                if name in self.active:
                    status = self.events[self.active[name]]["status"]
                elif not self.armed:
                    status = "PAUSED"
                else:
                    status = "OBSERVING" if device.impact_at_ms is not None else "MONITORING"
            devices[name] = {
                "online": online, "status": status, "last_seen_ms": device.last_seen_ms,
                "telemetry": asdict(device.telemetry) if device.telemetry else None,
            }
        return {
            "service": "ONLINE", "at_ms": now_ms, "revision": self.revision,
            "armed": self.armed, "config": asdict(self.config),
            "devices": devices, "events": list(self.events.values()),
        }
