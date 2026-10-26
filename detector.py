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
        print(f"ID awal dashboard: {project_id()}", flush=True)
        print("Mode banyak ruang: ID baru diterima otomatis, tidak perlu mengubah .env.", flush=True)
        print("Samakan ID dan broker di kedua HP; pilih ID yang sama di dashboard untuk memantaunya. Ctrl+C untuk berhenti.\n", flush=True)
        Service().run()
    except KeyboardInterrupt:
        print("\nBuddyCheck dihentikan.")
    except OSError as exc:
        if exc.errno in (98, 48, 10048, 10013) or getattr(exc, "winerror", None) in (10048, 10013):
            raise SystemExit("Port dashboard sudah dipakai atau tidak tersedia. Pastikan hanya satu run.bat/detector berjalan; tutup detector lama sebelum mencoba lagi.") from exc
        raise SystemExit(f"BuddyCheck gagal berjalan: {exc}. Periksa port dan koneksi internet.") from exc
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"BuddyCheck gagal berjalan: {exc}. Periksa .env, port, dan koneksi internet.") from exc
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    run()
