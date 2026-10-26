"""Deterministic in-memory flow preview; no MQTT and no physical phone data."""
from buddycheck import BuddyCheck
from shared.messages import Command, Telemetry


def run():
    engine = BuddyCheck()
    now = 1_000_000
    print("SIMULASI OFFLINE — bukan pengujian sensor HP atau MQTT cloud\n")
    for sequence in range(7):
        now += 1000
        impact = sequence == 0
        reading = Telemetry("edge1", "demo", sequence, now, 10 if impact else 0.1,
                            0.8 if impact else 0.01, 14 if impact else 0.2, 1000, 20, "simulator")
        engine.accept(reading, now)
    event = next(iter(engine.events.values()))
    print("A: lonjakan + rotasi, kemudian diam 5 detik")
    print("B menerima:", event["status"])
    for action, actor in (("REQUEST_STATUS", "edge2"), ("SAFE", "edge1")):
        now += 1000
        engine.command(Command(action, action, actor, event["event_id"], now), now)
        print(f"{actor} mengirim {action} -> {event['status']}")
    print("\nAlur berhasil. Lanjutkan uji dua HP fisik memakai panduan README.")


if __name__ == "__main__":
    run()
