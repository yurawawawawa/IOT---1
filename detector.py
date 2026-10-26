"""Laptop entry point: local dashboard + cloud MQTT detector."""

from shared.dashboard_server import start_dashboard_server
from shared.mqtt_connection import project_id
from service import Service


def run():
    server = thread = None
    try:
        server, thread = start_dashboard_server()
        print("\nBuddyCheck | Two-way activity check-in", flush=True)
        print(f"Dashboard: http://localhost:{server.server_port}/?view=dashboard", flush=True)
        print(f"PROJECT_ID: {project_id()}", flush=True)
        print("Gunakan ID dan broker yang sama di kedua HP. Ctrl+C untuk berhenti.\n", flush=True)
        Service().run()
    except KeyboardInterrupt:
        print("\nBuddyCheck dihentikan.")
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"BuddyCheck gagal berjalan: {exc}. Periksa .env, port, dan koneksi internet.") from exc
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    run()
