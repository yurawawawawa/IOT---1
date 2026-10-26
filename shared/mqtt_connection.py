"""BuddyCheck broker configuration and MQTT client construction."""

from dataclasses import dataclass, field
from ipaddress import ip_address
import os
from pathlib import Path
import re
from uuid import uuid4

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_HOST = "broker.hivemq.com"
DEFAULT_PROJECT_ID = "buddycheck_ganti_dengan_id_kelompok"


def project_id() -> str:
    candidate = os.environ.get("PROJECT_ID", DEFAULT_PROJECT_ID)
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", candidate) is None:
        raise ValueError("PROJECT_ID harus 1–80 karakter: huruf ASCII, angka, _ atau -")
    return candidate


def topic(suffix: str) -> str:
    return "/".join(("buddycheck", project_id(), suffix))


@dataclass(frozen=True)
class BrokerSettings:
    host: str
    port: int
    encrypted: bool
    username: str = ""
    password: str = field(default="", repr=False)

    @classmethod
    def from_env(cls):
        tls = os.environ.get("MQTT_TLS", "true").strip().lower()
        if tls not in ("true", "false"):
            raise ValueError("MQTT_TLS harus true atau false")
        encrypted = tls == "true"
        host = os.environ.get("MQTT_HOST", "").strip() or DEFAULT_HOST
        port = int(os.environ.get("MQTT_PORT") or (8883 if encrypted else 1883))
        if not 1 <= port <= 65535:
            raise ValueError("MQTT_PORT di luar rentang 1–65535")
        if not encrypted:
            try:
                loopback = ip_address(host).is_loopback
            except ValueError:
                loopback = host.casefold() == "localhost"
            if not loopback or os.environ.get("ALLOW_INSECURE_LOCAL") != "true":
                raise ValueError("MQTT tanpa TLS hanya untuk broker loopback dengan ALLOW_INSECURE_LOCAL=true")
        return cls(host, port, encrypted, os.environ.get("MQTT_USERNAME", ""), os.environ.get("MQTT_PASSWORD", ""))


def create_client(role: str, will: tuple[str, str] | None = None) -> mqtt.Client:
    project_id()
    settings = BrokerSettings.from_env()
    connection = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"bc-{role}-{uuid4().hex[:16]}",
        clean_session=True,
        protocol=mqtt.MQTTv311,
    )
    connection.connect_timeout = 8
    connection.reconnect_delay_set(min_delay=1, max_delay=20)
    if settings.encrypted:
        connection.tls_set()
    if settings.username:
        connection.username_pw_set(settings.username, settings.password)
    if will:
        address, payload = will
        connection.will_set(address, payload=payload, retain=True, qos=1)
    connection.connect(settings.host, port=settings.port, keepalive=30)
    return connection
