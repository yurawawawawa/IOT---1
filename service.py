"""MQTT adapter with independent BuddyCheck state for each user-created room."""

from dataclasses import dataclass, field
import json
import queue
import time
import uuid

from buddycheck import BuddyCheck, Config, SensorSessionConflict
from shared.messages import Command, Telemetry
from shared.mqtt_connection import create_client, project_id, topic, validate_project_id


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Room:
    engine: BuddyCheck
    last_activity_ms: int
    published_revision: int = -1
    last_publish: float = 0.0
    conflict_boots: dict[str, str] = field(default_factory=dict)


class Service:
    def __init__(self, engine: BuddyCheck | None = None, *, config: Config | None = None, max_rooms: int = 32, idle_seconds: float = 900):
        if max_rooms < 1 or idle_seconds <= 0:
            raise ValueError("Batas ruang dan durasi idle harus positif")
        self.default_group = project_id()
        self.config = engine.config if engine is not None else config or Config.from_env()
        self.rooms: dict[str, Room] = {}
        if engine is not None:
            self.rooms[self.default_group] = Room(engine, now_ms())
        self.max_rooms = max_rooms
        self.idle_ms = idle_seconds * 1000
        self.session = uuid.uuid4().hex
        self.presence_topic = f"buddycheck/_service/{self.session}"
        self.inbox = queue.Queue(maxsize=1024)
        self.client = None

    def _expire_rooms(self, timestamp: int):
        expired = [group for group, room in self.rooms.items() if timestamp - room.last_activity_ms >= self.idle_ms]
        for group in expired:
            if self.client is not None and self.client.is_connected():
                self.client.publish(topic("state", group), json.dumps({
                    "service": "OFFLINE", "project_id": group, "session_id": self.session,
                }), qos=1, retain=True)
            del self.rooms[group]

    def _room(self, group: str, timestamp: int) -> Room:
        if group not in self.rooms:
            self._expire_rooms(timestamp)
            if len(self.rooms) >= self.max_rooms:
                raise ValueError("Detector sedang penuh. Coba lagi setelah ruang yang tidak aktif berakhir.")
            self.rooms[group] = Room(BuddyCheck(self.config), timestamp)
            print(f"[ROOM] Ruang {group} dibuat otomatis", flush=True)
        return self.rooms[group]

    @staticmethod
    def _route(message_topic: str) -> tuple[str, str, str]:
        parts = message_topic.split("/")
        if len(parts) < 4 or parts[0] != "buddycheck":
            raise ValueError("Topic BuddyCheck tidak dikenal")
        group = validate_project_id(parts[1])
        if len(parts) == 5 and parts[2] == "edge" and parts[4] == "telemetry":
            return group, "telemetry", parts[3]
        if len(parts) == 4 and parts[2] == "commands":
            return group, "command", parts[3]
        raise ValueError("Topic BuddyCheck tidak dikenal")

    def handle(self, message_topic: str, payload: bytes, retained: bool, timestamp: int) -> dict | None:
        """Validate before allocating a room; commands and sensor data stay in that room."""
        if retained:
            raise ValueError("Telemetri/perintah retained diabaikan")
        group, kind, sender = self._route(message_topic)
        if kind == "telemetry":
            reading = Telemetry.from_json(payload)
            if sender != reading.device_id:
                raise ValueError("Device ID berbeda dari topic")
            if abs(timestamp - reading.sent_at_ms) > 15_000:
                raise ValueError("Telemetri kedaluwarsa; periksa jam HP")
            room = self._room(group, timestamp)
            try:
                opened = room.engine.accept(reading, timestamp)
            except SensorSessionConflict as exc:
                if room.conflict_boots.get(sender) != reading.boot_id:
                    print(f"[CONFLICT] {group}/{sender}: {exc}", flush=True)
                    room.conflict_boots[sender] = reading.boot_id
                return {
                    "kind": "telemetry", "ok": False, "code": "SENSOR_SESSION_CONFLICT",
                    "actor": sender, "boot_id": reading.boot_id,
                    "project_id": group, "reason": str(exc),
                }
            room.last_activity_ms = timestamp
            if opened:
                print(f"[EVENT] {group}/{reading.device_id}: CHECK YOUR BUDDY", flush=True)
            return None

        command = Command.from_json(payload)
        if sender != command.actor:
            raise ValueError("Actor berbeda dari topic")
        receipt = {"command_id": command.command_id, "actor": command.actor, "project_id": group}
        try:
            if abs(timestamp - command.sent_at_ms) > 15_000:
                raise ValueError("Perintah kedaluwarsa")
            if command.action in ("ARM", "DISARM") and command.actor != "dashboard":
                raise ValueError("Monitoring diatur dari dashboard")
            if command.action not in ("JOIN", "ARM", "DISARM") and group not in self.rooms:
                raise ValueError("Ruang belum aktif. Hubungkan ulang perangkat terlebih dahulu.")
            room = self._room(group, timestamp)
            changed = command.action == "JOIN" or room.engine.command(command, timestamp)
            room.last_activity_ms = timestamp
            receipt.update(ok=True, duplicate=not changed)
        except ValueError as exc:
            receipt.update(ok=False, reason=str(exc))
        return receipt

    def publish_state(self, group: str):
        state = self.rooms[group].engine.snapshot(now_ms())
        state.update(session_id=self.session, project_id=group, service_topic=self.presence_topic)
        self.client.publish(topic("state", group), json.dumps(state), qos=1, retain=True)

    def run(self):
        offline = json.dumps({"service": "OFFLINE", "session_id": self.session})
        self.client = create_client("detector", will=(self.presence_topic, offline))

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                print(f"[MQTT] Koneksi ditolak: {reason_code}", flush=True)
                return
            client.subscribe([("buddycheck/+/edge/+/telemetry", 1), ("buddycheck/+/commands/+", 1)])
            client.publish(self.presence_topic, json.dumps({"service": "ONLINE", "session_id": self.session}), qos=1, retain=True)
            try:
                self.inbox.put_nowait(None)
            except queue.Full:
                pass
            print("[MQTT] Detector terhubung; menerima ID ruang secara otomatis.", flush=True)

        def on_message(client, userdata, message):
            if len(message.payload) > 16_384:
                return
            try:
                self.inbox.put_nowait((message.topic, message.payload, message.retain, now_ms()))
            except queue.Full:
                print("[MQTT] Antrean penuh; satu pesan diabaikan.", flush=True)

        self.client.on_connect = on_connect
        self.client.on_message = on_message
        self.client.loop_start()
        try:
            while True:
                try:
                    message = self.inbox.get(timeout=0.2)
                    if message is None:
                        if not self.rooms:
                            self._room(self.default_group, now_ms())
                        for room in self.rooms.values():
                            room.published_revision = -1
                    else:
                        try:
                            receipt = self.handle(*message)
                            if receipt:
                                address = topic(f"receipts/{receipt['actor']}", receipt["project_id"])
                                self.client.publish(address, json.dumps(receipt), qos=1)
                        except (ValueError, TypeError) as exc:
                            print(f"[REJECTED] {exc}", flush=True)
                except queue.Empty:
                    pass
                self._expire_rooms(now_ms())
                clock = time.monotonic()
                for group, room in self.rooms.items():
                    room.engine.tick(now_ms())
                    if self.client.is_connected() and (
                        room.engine.revision != room.published_revision or clock - room.last_publish >= 1
                    ):
                        self.publish_state(group)
                        room.published_revision = room.engine.revision
                        room.last_publish = clock
        finally:
            try:
                for group in self.rooms:
                    self.client.publish(topic("state", group), json.dumps({
                        "service": "OFFLINE", "session_id": self.session, "project_id": group,
                    }), qos=1, retain=True)
                info = self.client.publish(self.presence_topic, offline, qos=1, retain=True)
                info.wait_for_publish(timeout=2)
            except (ValueError, RuntimeError):
                pass
            self.client.disconnect()
            self.client.loop_stop()
