from dataclasses import asdict, replace
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from buddycheck import Config
from service import Service
from shared.messages import Command, Telemetry
from shared.mqtt_connection import topic


class RoomTests(TestCase):
    def setUp(self):
        self.service = Service(config=Config(still_seconds=1, observation_seconds=6))
        self.clock = 1_000_000
        self.sequence = {}
        self.command_sequence = 0

    def command(self, group, action="JOIN", actor="dashboard", event_id="", command_id=None):
        self.command_sequence += 1
        command = Command(command_id or f"cmd{self.command_sequence}", action, actor, event_id, self.clock)
        return self.service.handle(topic(f"commands/{actor}", group), json.dumps(asdict(command)).encode(), False, self.clock)

    def feed(self, group, device="edge1", impact=False):
        self.clock += 1000
        key = (group, device)
        self.sequence[key] = self.sequence.get(key, 0) + 1
        reading = Telemetry(device, "sameboot", self.sequence[key], self.clock,
                            10 if impact else 0.1, 0.8 if impact else 0.01,
                            14 if impact else 0.2, 1000, 20, "simulator")
        self.service.handle(topic(f"edge/{device}/telemetry", group), reading.to_json().encode(), False, self.clock)

    def incident(self, group):
        self.feed(group, impact=True)
        self.feed(group)
        self.feed(group)
        return next(iter(self.service.rooms[group].engine.events.values()))

    def test_user_id_does_not_have_to_match_env_default(self):
        receipt = self.command("nama_bebas_123")
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["project_id"], "nama_bebas_123")
        self.assertIn("nama_bebas_123", self.service.rooms)

    def test_telemetry_creates_room_for_older_clients_without_join(self):
        self.feed("tanpa_join")
        self.assertIn("edge1", self.service.rooms["tanpa_join"].engine.devices)
        self.assertIsNotNone(self.service.rooms["tanpa_join"].engine.devices["edge1"].telemetry)

    def test_replaced_sensor_gets_scoped_conflict_receipt_without_repeated_logs(self):
        self.feed("argayura")
        old = self.service.rooms["argayura"].engine.devices["edge1"].telemetry
        self.clock += 1000
        current = replace(old, boot_id="replacement", sequence=0, sent_at_ms=self.clock)
        address = topic("edge/edge1/telemetry", "argayura")
        self.service.handle(address, current.to_json().encode(), False, self.clock)
        with patch("builtins.print") as logger:
            for index in range(2):
                self.clock += 1000
                stale = replace(old, sequence=old.sequence + index + 1, sent_at_ms=self.clock)
                receipt = self.service.handle(address, stale.to_json().encode(), False, self.clock)
                self.assertEqual(receipt["code"], "SENSOR_SESSION_CONFLICT")
                self.assertEqual((receipt["actor"], receipt["boot_id"], receipt["project_id"]),
                                 ("edge1", "sameboot", "argayura"))
                self.assertFalse(receipt["ok"])
            self.assertEqual(logger.call_count, 1)
        self.assertEqual(self.service.rooms["argayura"].engine.devices["edge1"].telemetry, current)

    def test_different_ids_do_not_pair_phones(self):
        self.feed("kelompok_a", "edge1")
        self.feed("kelompok_b", "edge2")
        a = self.service.rooms["kelompok_a"].engine.snapshot(self.clock)
        b = self.service.rooms["kelompok_b"].engine.snapshot(self.clock)
        self.assertTrue(a["devices"]["edge1"]["online"])
        self.assertFalse(a["devices"]["edge2"]["online"])
        self.assertFalse(b["devices"]["edge1"]["online"])
        self.assertTrue(b["devices"]["edge2"]["online"])

    def test_same_boot_and_sequence_are_independent_between_rooms(self):
        self.feed("a")
        self.feed("b")
        for group in ("a", "b"):
            self.assertEqual(self.service.rooms[group].engine.devices["edge1"].telemetry.sequence, 1)

    def test_events_and_replies_cannot_cross_rooms(self):
        event = self.incident("ruang_a")
        self.command("ruang_b")
        wrong = self.command("ruang_b", "REQUEST_STATUS", "edge2", event["event_id"])
        self.assertFalse(wrong["ok"])
        self.assertEqual(event["status"], "CHECK_BUDDY")
        self.assertFalse(self.service.rooms["ruang_b"].engine.events)
        self.assertTrue(self.command("ruang_a", "REQUEST_STATUS", "edge2", event["event_id"])["ok"])
        self.assertTrue(self.command("ruang_a", "SAFE", "edge1", event["event_id"])["ok"])
        self.assertEqual(event["status"], "SAFE")

    def test_pause_and_command_deduplication_are_per_room(self):
        self.command("a")
        self.command("b")
        self.command("a", "DISARM", command_id="samecommand")
        self.assertFalse(self.service.rooms["a"].engine.armed)
        self.assertTrue(self.service.rooms["b"].engine.armed)
        self.command("b", "DISARM", command_id="samecommand")
        self.assertFalse(self.service.rooms["b"].engine.armed)

    def test_invalid_and_retained_messages_do_not_allocate_rooms(self):
        payload = json.dumps(asdict(Command("c", "JOIN", "dashboard", "", self.clock))).encode()
        for address, data, retained in (
            ("buddycheck/invalid+id/commands/dashboard", payload, False),
            ("buddycheck/a/state", payload, False),
            ("buddycheck/a/commands/edge1", payload, False),
            ("buddycheck/a/commands/dashboard", payload, True),
            ("buddycheck/a/edge/edge1/telemetry", b"{}", False),
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.service.handle(address, data, retained, self.clock)
        self.assertFalse(self.service.rooms)

    def test_stale_join_does_not_allocate_a_room(self):
        payload = json.dumps(asdict(Command("c", "JOIN", "edge1", "", self.clock-16000))).encode()
        receipt = self.service.handle(topic("commands/edge1", "stale"), payload, False, self.clock)
        self.assertFalse(receipt["ok"])
        self.assertFalse(self.service.rooms)

    def test_unknown_event_does_not_create_a_room(self):
        self.assertFalse(self.command("new", "SAFE", "edge1", "unknown_event")["ok"])
        self.assertFalse(self.service.rooms)

    def test_room_limit_and_idle_cleanup_bound_memory(self):
        self.service = Service(max_rooms=2, idle_seconds=10)
        self.assertTrue(self.command("a")["ok"])
        self.assertTrue(self.command("b")["ok"])
        self.assertFalse(self.command("c")["ok"])
        self.clock += 10001
        self.assertTrue(self.command("c")["ok"])
        self.assertEqual(set(self.service.rooms), {"c"})

    def test_join_heartbeat_keeps_room_alive(self):
        self.service = Service(idle_seconds=10)
        self.command("a")
        self.clock += 9000
        self.command("a")
        self.service._expire_rooms(self.clock + 2000)
        self.assertIn("a", self.service.rooms)

    def test_published_state_contains_only_selected_room(self):
        self.incident("a")
        self.command("b")
        self.service.client = MagicMock()
        with patch("service.now_ms", return_value=self.clock):
            self.service.publish_state("b")
        address, encoded = self.service.client.publish.call_args.args
        state = json.loads(encoded)
        self.assertEqual(address, topic("state", "b"))
        self.assertEqual(state["project_id"], "b")
        self.assertEqual(state["events"], [])
        self.assertEqual(state["service_topic"], self.service.presence_topic)
