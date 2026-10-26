from http.client import HTTPConnection
import json
import os
from unittest import TestCase
from unittest.mock import patch

from shared.dashboard_server import public_browser_config, start_dashboard_server


class DashboardTests(TestCase):
    def test_browser_config_never_exposes_server_credentials(self):
        with patch.dict(os.environ, {"PROJECT_ID": "private_test", "MQTT_USERNAME": "private-user", "MQTT_PASSWORD": "test-secret"}):
            config = public_browser_config()
            self.assertFalse(config["automatic_connection"])
            serialized = json.dumps(config)
            self.assertNotIn("test-secret", serialized)
            self.assertNotIn("private-user", serialized)

    def test_only_web_assets_and_public_config_are_served(self):
        with patch.dict(os.environ, {"DASHBOARD_HOST": "127.0.0.1", "PROJECT_ID": "server_test"}):
            server, thread = start_dashboard_server(port=0)
            try:
                for path, expected in (("/", 200), ("/app.js", 200), ("/config.json", 200), ("/.env", 404), ("/../.env", 404), ("/vendor/", 403)):
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    try:
                        connection.request("GET", path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, expected, path)
                        if path == "/config.json":
                            self.assertEqual(json.loads(response.read())["project_id"], "server_test")
                    finally:
                        connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
