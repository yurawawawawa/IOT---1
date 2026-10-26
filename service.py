"""MQTT adapter. Only the main thread mutates the BuddyCheck engine."""

import json
import queue
import time
import uuid

from buddycheck import BuddyCheck, Config
from shared.messages import Command, Telemetry
from shared.mqtt_connection import create_client, topic


def now_ms() -> int:
    return int(time.time() * 1000)


class Service:
    def __init__(self, engine: BuddyCheck | None = None):
        self.engine = engine or BuddyCheck(Config.from_env())
        self.session = uuid.uuid4().hex
        self.inbox = queue.Queue(maxsize=1024)
        self.client = None

    def handle(self, message_topic: str, payload: bytes, retained: bool, timestamp: int) -> dict | None:
        """Return command receipt; malformed sensor/command data never crashes the loop."""
        if retained:
            raise ValueError("Telemetri/perintah retained diabaikan")
        if message_topic.startswith(topic("edge/")):
            reading = Telemetry.from_json(payload)
            if message_topic != topic(f"edge/{reading.device_id}/telemetry"):
                raise ValueError("Device ID berbeda dari topic")
            opened = self.engine.accept(reading, timestamp)
            if opened:
                print(f"[EVENT] {reading.device_id}: CHECK YOUR BUDDY", flush=True)
            return None
        command = Command.from_json(payload)
        if message_topic != topic(f"commands/{command.actor}"):
            raise ValueError("Actor berbeda dari topic")
        try:
            changed = self.engine.command(command, timestamp)
            receipt = {"command_id": command.command_id, "ok": True, "duplicate": not changed}
        except ValueError as exc:
            receipt = {"command_id": command.command_id, "ok": False, "reason": str(exc)}
        receipt["actor"] = command.actor
        return receipt

    def publish_state(self):
        state = self.engine.snapshot(now_ms())
        state["session_id"] = self.session
        self.client.publish(topic("state"), json.dumps(state), qos=1, retain=True)

    def run(self):
        offline = json.dumps({"service": "OFFLINE", "session_id": self.session})
        self.client = create_client("detector", will=(topic("state"), offline))

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                print(f"[MQTT] Koneksi ditolak: {reason_code}", flush=True)
                return
            client.subscribe([(topic("edge/+/telemetry"), 1), (topic("commands/+"), 1)])
            self.inbox.put_nowait(None)
            print("[MQTT] Detector terhubung ke broker.", flush=True)

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
        last_published = 0.0
        published_revision = -1
        try:
            while True:
                try:
                    message = self.inbox.get(timeout=0.2)
                    if message is not None:
                        try:
                            receipt = self.handle(*message)
                            if receipt:
                                self.client.publish(topic(f"receipts/{receipt['actor']}"), json.dumps(receipt), qos=1)
                        except (ValueError, TypeError) as exc:
                            print(f"[REJECTED] {exc}", flush=True)
                except queue.Empty:
                    pass
                self.engine.tick(now_ms())
                clock = time.monotonic()
                if self.client.is_connected() and (
                    self.engine.revision != published_revision or clock - last_published >= 1
                ):
                    self.publish_state()
                    published_revision = self.engine.revision
                    last_published = clock
        finally:
            try:
                info = self.client.publish(topic("state"), offline, qos=1, retain=True)
                info.wait_for_publish(timeout=2)
            except (ValueError, RuntimeError):
                pass
            self.client.disconnect()
            self.client.loop_stop()
