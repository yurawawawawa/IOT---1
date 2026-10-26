"""Optional Termux sender. Primary interface is the HTTPS phone web page."""

import argparse
from dataclasses import asdict
import json
from threading import Thread
import time
import uuid

from shared.messages import Telemetry
from shared.mqtt_connection import create_client, topic
from shared.processing import extract_features
from shared.sensors import select_source


def main():
    parser = argparse.ArgumentParser(description="BuddyCheck edge Android / simulator eksplisit")
    parser.add_argument("--device", choices=("edge1", "edge2"), required=True)
    parser.add_argument("--source", choices=("android", "simulator"), default="android")
    parser.add_argument("--scenario", choices=("still", "incident"), default="still")
    args = parser.parse_args()
    sensor = select_source(args.source, args.scenario)
    client = create_client(args.device)
    boot_id = uuid.uuid4().hex
    event_states = {}

    def on_connect(client, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            client.subscribe([(topic("state"), 1), (topic(f"receipts/{args.device}"), 1)])

    def on_message(client, userdata, message):
        try:
            value = json.loads(message.payload)
            if message.topic.endswith("/state"):
                if value.get("service") != "ONLINE":
                    print("\n[DETECTOR] Offline", flush=True)
                for event in value.get("events", []):
                    if event_states.get(event["event_id"]) != event["status"]:
                        event_states[event["event_id"]] = event["status"]
                        print(f"\n[EVENT] {event['event_id']} | {event['subject']} | {event['status']}", flush=True)
            else:
                print(f"\n[RECEIPT] {value}", flush=True)
        except (ValueError, KeyError, TypeError):
            pass

    def commands():
        aliases = {"request": "REQUEST_STATUS", "safe": "SAFE", "help": "NEED_HELP", "done": "ACKNOWLEDGE"}
        print("Perintah: request EVENT_ID | safe EVENT_ID | help EVENT_ID | done EVENT_ID", flush=True)
        while True:
            try:
                parts = input().split()
            except (EOFError, OSError):
                return
            if len(parts) != 2 or parts[0] not in aliases:
                print("Gunakan request/safe/help/done diikuti EVENT_ID.", flush=True)
                continue
            if not client.is_connected():
                print("MQTT offline; perintah tidak dikirim.", flush=True)
                continue
            client.publish(topic(f"commands/{args.device}"), json.dumps({
                "command_id": uuid.uuid4().hex, "action": aliases[parts[0]],
                "actor": args.device, "event_id": parts[1], "sent_at_ms": int(time.time() * 1000),
            }), qos=1)

    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()
    Thread(target=commands, daemon=True).start()
    print(f"Source: {'SENSOR FISIK' if args.source == 'android' else 'SIMULASI — BUKAN SENSOR HP'}", flush=True)
    sequence = 0
    try:
        while True:
            samples = []
            started = time.monotonic()
            while len(samples) < 4 or time.monotonic() - started < 1:
                samples.append(sensor.read())
                time.sleep(0.05)
            features = extract_features(samples)
            if features.window_ms > 3000:
                print("Sensor terlalu lambat (>3 detik/window); coba browser HP.", flush=True)
                continue
            reading = Telemetry(
                args.device, boot_id, sequence, int(time.time() * 1000), **asdict(features),
                source="physical" if args.source == "android" else "simulator",
            )
            if client.is_connected():
                client.publish(topic(f"edge/{args.device}/telemetry"), reading.to_json(), qos=1)
                print(f"[{args.device}] RMS={features.motion_rms:.2f} rot={features.rotation_rad:.2f} peak={features.accel_peak:.2f}", flush=True)
            sequence += 1
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
