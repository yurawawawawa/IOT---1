import os
from unittest import TestCase
from unittest.mock import patch

from shared.mqtt_connection import BrokerSettings, project_id
from shared.processing import SensorSample, extract_features
from shared.sensors import TermuxSensors, _axes, select_source


class BackendTests(TestCase):
    def test_termux_channels_read_and_axis_mapping(self):
        inventory = {"sensors": ["Linear Acceleration", "Accelerometer Uncalibrated", "BMI Accelerometer", "BMI Gyroscope"]}
        packet = {"BMI Accelerometer": {"values": [0, 0, 9.81]}, "BMI Gyroscope": {"values": [0, 0.2, 0]}}
        with patch("shared.sensors.which", return_value="termux-sensor"), patch("shared.sensors._api", side_effect=[inventory, packet]):
            source = TermuxSensors()
            reading = source.read()
        self.assertEqual(reading.acceleration, (0.0, 0.0, 9.81))
        self.assertEqual(reading.gyroscope, (0.0, 0.2, 0.0))

    def test_invalid_hardware_values_are_rejected(self):
        for values in ([0, 0], [0, None, 0], [0, float("nan"), 0], [0, True, 0]):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                _axes({"values": values})

    def test_duplicate_sample_times_rejected(self):
        samples = [SensorSample(1.0, (0, 0, 9.81), (0, 0, 0)) for _ in range(4)]
        with self.assertRaises(ValueError): extract_features(samples)

    def test_nonfinite_processing_rejected(self):
        samples = [SensorSample(index / 4, (0, 0, float("inf")), (0, 0, 0)) for index in range(4)]
        with self.assertRaises(ValueError): extract_features(samples)

    def test_simulator_is_explicit_and_unknown_source_rejected(self):
        self.assertIsInstance(select_source("simulator", "still").read(), SensorSample)
        with self.assertRaises(ValueError): select_source("unknown", "still")

    def test_project_id_matches_browser_ascii_contract(self):
        for value in ("", "group/#", "kelompok-é", "a" * 81):
            with patch.dict(os.environ, {"PROJECT_ID": value}), self.assertRaises(ValueError): project_id()

    def test_insecure_broker_is_restricted_to_local_testing(self):
        with patch.dict(os.environ, {"MQTT_TLS": "false", "MQTT_HOST": "broker.example.com", "ALLOW_INSECURE_LOCAL": "true"}):
            with self.assertRaises(ValueError): BrokerSettings.from_env()
        with patch.dict(os.environ, {"MQTT_TLS": "false", "MQTT_HOST": "127.0.0.1", "ALLOW_INSECURE_LOCAL": "true"}):
            self.assertFalse(BrokerSettings.from_env().encrypted)

    def test_broker_repr_does_not_include_password(self):
        settings = BrokerSettings("localhost", 8883, True, "user", "secret-value")
        self.assertNotIn("secret-value", repr(settings))
