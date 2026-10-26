from dataclasses import asdict, replace
import json
import unittest

from buddycheck import BuddyCheck, Config
from shared.messages import Command, Telemetry
from shared.processing import SensorSample, extract_features
from service import Service
from shared.mqtt_connection import topic


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = BuddyCheck()
        self.clock = 1_000_000
        self.sequences = {"edge1": 0, "edge2": 0}

    def reading(self, device="edge1", impact=False, moving=False, boot="boot1", step=1000):
        self.clock += step
        self.sequences[device] += 1
        return Telemetry(device, boot, self.sequences[device], self.clock,
                         10 if impact else 2 if moving else 0.1,
                         0.8 if impact else 0.3 if moving else 0.01,
                         14 if impact else 2 if moving else 0.2, 1000, 20, "physical")

    def feed(self, **kwargs):
        reading = self.reading(**kwargs)
        return self.engine.accept(reading, self.clock)

    def incident(self, device="edge1"):
        self.feed(device=device, impact=True)
        for _ in range(6):
            self.feed(device=device)
        return next(reversed(self.engine.events.values()))

    def command(self, action, actor, event, command_id=None):
        return Command(command_id or f"command{self.clock}{action}", action, actor, event["event_id"], self.clock)

    def test_still_and_walking_do_not_trigger(self):
        for _ in range(20):
            self.feed(moving=True)
            self.feed()
        self.assertFalse(self.engine.events)

    def test_impact_without_rotation_does_not_trigger(self):
        reading = replace(self.reading(impact=True), rotation_rad=0.01)
        self.engine.accept(reading, self.clock)
        for _ in range(8): self.feed()
        self.assertFalse(self.engine.events)

    def test_rotation_without_peak_does_not_trigger(self):
        reading = replace(self.reading(impact=True), accel_peak=0.2)
        self.engine.accept(reading, self.clock)
        for _ in range(8): self.feed()
        self.assertFalse(self.engine.events)

    def test_impact_then_continuous_stillness_triggers(self):
        self.feed(impact=True)
        for _ in range(5): self.assertFalse(self.feed())
        self.assertTrue(self.feed())
        self.assertEqual(next(iter(self.engine.events.values()))["status"], "CHECK_BUDDY")

    def test_both_devices_are_symmetric_and_independent(self):
        for device, buddy in (("edge1", "edge2"), ("edge2", "edge1")):
            event = self.incident(device)
            self.assertEqual((event["subject"], event["buddy"]), (device, buddy))
        self.assertEqual(len(self.engine.active), 2)

    def test_movement_interrupts_still_duration(self):
        self.feed(impact=True)
        for _ in range(4): self.feed()
        self.feed(moving=True)
        for _ in range(5): self.assertFalse(self.feed())
        self.assertTrue(self.feed())

    def test_observation_expires(self):
        self.feed(impact=True)
        for _ in range(13): self.feed(moving=True)
        for _ in range(6): self.feed()
        self.assertFalse(self.engine.events)

    def test_missing_sensor_data_is_not_stillness(self):
        self.feed(impact=True)
        self.feed()
        self.feed(step=4000)
        for _ in range(6): self.feed()
        self.assertFalse(self.engine.events)

    def test_restart_clears_candidate(self):
        self.feed(impact=True)
        self.feed(boot="newboot")
        for _ in range(6): self.feed(boot="newboot")
        self.assertFalse(self.engine.events)
        with self.assertRaises(ValueError): self.feed(boot="boot1")

    def test_replay_rejected(self):
        reading = self.reading()
        self.engine.accept(reading, self.clock)
        with self.assertRaises(ValueError): self.engine.accept(reading, self.clock)

    def test_retired_sender_does_not_break_detection_for_current_session(self):
        self.feed()
        self.feed(boot="newboot", impact=True)
        for _ in range(6):
            with self.assertRaises(ValueError): self.feed(boot="boot1", step=100)
            self.feed(boot="newboot", step=900)
        self.assertEqual(next(iter(self.engine.events.values()))["status"], "CHECK_BUDDY")

    def test_detector_restart_accepts_existing_phone_session(self):
        self.feed()
        self.engine = BuddyCheck()
        self.feed(impact=True)
        for _ in range(6): self.feed()
        self.assertEqual(len(self.engine.events), 1)

    def test_old_timestamp_rejected(self):
        reading = self.reading()
        with self.assertRaises(ValueError): self.engine.accept(reading, self.clock + 16000)

    def test_request_and_safe(self):
        event = self.incident()
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.assertEqual(event["status"], "AWAITING_REPLY")
        self.engine.command(self.command("SAFE", "edge1", event), self.clock)
        self.assertEqual(event["status"], "SAFE")
        self.assertFalse(self.engine.active)

    def test_need_help_stays_active_until_acknowledged(self):
        event = self.incident()
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.engine.command(self.command("NEED_HELP", "edge1", event), self.clock)
        self.assertIn("edge1", self.engine.active)
        self.engine.command(self.command("ACKNOWLEDGE", "edge2", event), self.clock)
        self.assertEqual(event["status"], "CLOSED")

    def test_wrong_actor_rejected(self):
        event = self.incident()
        with self.assertRaises(ValueError): self.engine.command(self.command("REQUEST_STATUS", "edge1", event), self.clock)
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        for actor in ("edge2", "dashboard"):
            with self.assertRaises(ValueError): self.engine.command(self.command("SAFE", actor, event), self.clock)

    def test_safe_without_request_rejected(self):
        event = self.incident()
        with self.assertRaises(ValueError): self.engine.command(self.command("SAFE", "edge1", event), self.clock)

    def test_duplicate_command_is_idempotent(self):
        event = self.incident()
        command = self.command("REQUEST_STATUS", "edge2", event)
        self.assertTrue(self.engine.command(command, self.clock))
        self.assertFalse(self.engine.command(command, self.clock))

    def test_late_answer_rejected(self):
        event = self.incident()
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.clock += 30000
        with self.assertRaises(ValueError): self.engine.command(self.command("SAFE", "edge1", event), self.clock)
        self.assertEqual(event["status"], "NO_RESPONSE")

    def test_check_without_request_also_times_out(self):
        event = self.incident()
        self.engine.tick(self.clock + 60000)
        self.assertEqual(event["status"], "NO_RESPONSE")

    def test_timeout_can_be_requested_again(self):
        event = self.incident()
        self.clock += 60000
        self.engine.tick(self.clock)
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.assertEqual(event["status"], "AWAITING_REPLY")

    def test_offline_separate_from_response_timeout(self):
        event = self.incident()
        state = self.engine.snapshot(self.clock + 8000)
        self.assertEqual(state["devices"]["edge1"]["status"], "OFFLINE")
        self.assertEqual(event["status"], "CHECK_BUDDY")

    def test_pending_incident_does_not_repeat(self):
        self.incident()
        for _ in range(10): self.feed(impact=True)
        self.assertEqual(len(self.engine.events), 1)

    def test_pause_clears_candidate_but_allows_reply(self):
        event = self.incident()
        self.engine.command(Command("pause", "DISARM", "dashboard", "", self.clock), self.clock)
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.engine.command(self.command("SAFE", "edge1", event), self.clock)
        for _ in range(8): self.feed(impact=True)
        self.assertEqual(len(self.engine.events), 1)

    def test_cooldown_prevents_immediate_realert(self):
        event = self.incident()
        self.engine.command(self.command("REQUEST_STATUS", "edge2", event), self.clock)
        self.engine.command(self.command("SAFE", "edge1", event), self.clock)
        self.feed(impact=True)
        for _ in range(6): self.feed()
        self.assertEqual(len(self.engine.events), 1)

    def test_simulation_source_stays_visible(self):
        reading = replace(self.reading(), source="simulator")
        self.engine.accept(reading, self.clock)
        self.assertEqual(self.engine.snapshot(self.clock)["devices"]["edge1"]["telemetry"]["source"], "simulator")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.reading = Telemetry("edge1", "boot", 0, 10000, 0.1, 0.01, 0.2, 1000, 20)

    def test_round_trip(self):
        self.assertEqual(Telemetry.from_json(self.reading.to_json()), self.reading)

    def test_malformed_numbers_rejected(self):
        for key, value in (("motion_rms", float("nan")), ("accel_peak", -1), ("sequence", True), ("sample_count", 1), ("window_ms", 9000), ("source", "unknown")):
            payload = {**asdict(self.reading), key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): Telemetry.from_json(json.dumps(payload))

    def test_wrong_topic_and_retained_rejected(self):
        service = Service(BuddyCheck())
        for address, retained in ((topic("edge/edge2/telemetry"), False), (topic("edge/edge1/telemetry"), True)):
            with self.assertRaises(ValueError): service.handle(address, self.reading.to_json().encode(), retained, 10000)

    def test_command_topic_actor_must_match(self):
        command = json.dumps(dict(command_id="test", action="ARM", actor="dashboard", sent_at_ms=10000)).encode()
        with self.assertRaises(ValueError): Service(BuddyCheck()).handle(topic("commands/edge1"), command, False, 10000)

    def test_bad_config_rejected(self):
        for kwargs in ({"impact_peak": float("nan")}, {"offline_seconds": 0}, {"still_seconds": 15}):
            with self.assertRaises(ValueError): Config(**kwargs)


class ProcessingTests(unittest.TestCase):
    def test_physical_units_and_peak(self):
        samples = [SensorSample(index / 4, (0, 0, 9.81 + (4 if index == 2 else 0)), (0, 0, 2)) for index in range(5)]
        result = extract_features(samples)
        self.assertAlmostEqual(result.motion_rms, 1.7889, places=4)
        self.assertEqual((result.rotation_rad, result.accel_peak, result.window_ms, result.sample_count), (2.0, 4.0, 1000, 5))


if __name__ == "__main__":
    unittest.main()
