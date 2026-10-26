"""Check actual configured MQTT/TLS and browser WSS paths with a disposable probe."""

import os
from threading import Event
import uuid
from urllib.parse import urlsplit

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from shared.mqtt_connection import project_id, topic


def check(transport: str):
    is_ws = transport == "websockets"
    url = urlsplit(os.getenv("MQTT_WS_URL", "wss://broker.hivemq.com:8884/mqtt"))
    if is_ws and url.scheme != "wss":
        raise ValueError("Pemeriksaan cloud memerlukan MQTT_WS_URL wss://")
    host = url.hostname if is_ws else os.getenv("MQTT_HOST", "broker.hivemq.com")
    port = url.port or 443 if is_ws else int(os.getenv("MQTT_PORT", "8883"))
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bc-probe-" + uuid.uuid4().hex[:12], transport=transport)
    client.connect_timeout = 6
    client.tls_set()
    if is_ws:
        client.ws_set_options(path=url.path or "/mqtt")
    if os.getenv("MQTT_USERNAME"):
        client.username_pw_set(os.environ["MQTT_USERNAME"], os.getenv("MQTT_PASSWORD", ""))
    probe_topic = topic("diagnostics/" + uuid.uuid4().hex)
    finished = Event()
    result = []

    def connected(client, userdata, flags, reason, properties):
        if reason.is_failure:
            result.append(str(reason)); finished.set()
        else:
            client.subscribe(probe_topic, qos=1)

    def subscribed(client, userdata, mid, reasons, properties):
        client.publish(probe_topic, "buddycheck-connectivity-test", qos=1, retain=False)

    def received(client, userdata, message):
        if message.topic == probe_topic and message.payload == b"buddycheck-connectivity-test":
            result.append("OK"); finished.set()

    client.on_connect = connected
    client.on_subscribe = subscribed
    client.on_message = received
    try:
        client.connect(host, port, keepalive=15)
        client.loop_start()
        if not finished.wait(10):
            raise TimeoutError("Tidak menerima echo dari broker")
        if result != ["OK"]:
            raise RuntimeError(str(result))
        print(f"PASS {transport}: {host}:{port} publish/subscribe TLS berhasil.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    load_dotenv()
    print(f"Uji koneksi cloud, PROJECT_ID={project_id()}; hanya probe teks, bukan data sensor.")
    failures = []
    for transport in ("tcp", "websockets"):
        try:
            check(transport)
        except (OSError, ValueError, RuntimeError) as exc:
            failures.append(transport)
            print(f"FAIL {transport}: {exc}")
    if failures:
        raise SystemExit(1)
