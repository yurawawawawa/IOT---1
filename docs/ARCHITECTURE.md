# Arsitektur BuddyCheck

```text
WiFi/hotspot yang sama
  HP A: accelerometer + gyroscope -> RMS, rotasi, peak
  HP B: accelerometer + gyroscope -> RMS, rotasi, peak
  Laptop: detector Python + server dashboard lokal

HP A -- MQTT/WSS --> Broker MQTT cloud <-- MQTT/WSS -- HP B
                           ^    |
                           |    v
                  Detector laptop (MQTT/TLS)
                           |
                      state -> cloud -> kedua HP + dashboard
                      commands <- cloud <- HP / dashboard
```

Hosting HTTPS hanya menyajikan HTML/CSS/JS HP. Hosting ini tidak menjalankan detector. Detector tetap harus hidup di laptop. Broker cloud meneruskan pesan; tidak ada database/cloud function yang diperlukan untuk versi awal ini.

## Prinsip BuddyCheck

BuddyCheck memeriksa urutan gerakan **setiap pengguna secara independen** dan memberikan peran timbal balik yang sama. Kedua HP bisa memiliki kejadian aktif bersamaan. Konfirmasi berlangsung melalui cloud dengan korelasi `event_id`.

## Topik MQTT

Namespace: `buddycheck/PROJECT_ID/`.

| Suffix | Publisher | Subscriber | Retain |
|---|---|---|---|
| `edge/edge1/telemetry` | HP A | Detector | Tidak |
| `edge/edge2/telemetry` | HP B | Detector | Tidak |
| `commands/edge1` | HP A | Detector | Tidak |
| `commands/edge2` | HP B | Detector | Tidak |
| `commands/dashboard` | Dashboard, ARM/DISARM | Detector | Tidak |
| `receipts/edge1`, `receipts/edge2`, `receipts/dashboard` | Detector | Pengirim perintah | Tidak |
| `state` | Detector | Semua UI | Ya |

Semua publish menggunakan QoS 1. Duplikasi telemetri disaring dengan boot ID dan sequence. Command memakai UUID dan cache deduplikasi. Pesan retained telemetri/perintah diabaikan agar aksi lama tidak berjalan saat subscribe. Last Will detector mengirim `service: OFFLINE` pada topik state.

## Telemetri

```json
{
  "device_id": "edge1",
  "boot_id": "uuid_tanpa_tanda_hubung",
  "sequence": 42,
  "sent_at_ms": 1790000000000,
  "motion_rms": 1.12,
  "rotation_rad": 0.45,
  "accel_peak": 9.2,
  "window_ms": 1020,
  "sample_count": 21,
  "source": "physical"
}
```

Timestamp contoh bukan untuk dikirim ulang: detector menolak selisih jam >15 detik. Semua angka harus finite dan nonnegatif. Jendela valid 100–3000 ms dengan minimal 4 sampel. Hanya `edge1` dan `edge2` diterima. Session baru menghapus kandidat deteksi dari sesi sebelumnya.

## State machine

```text
MONITORING -> OBSERVING (peak dan rotasi melampaui ambang)
OBSERVING -> MONITORING (observasi kedaluwarsa / sampel terputus)
OBSERVING -> CHECK_BUDDY (diam berkelanjutan memenuhi durasi)
CHECK_BUDDY -> AWAITING_REPLY (REQUEST_STATUS dari teman)
AWAITING_REPLY -> SAFE (jawaban pengguna yang diperiksa)
AWAITING_REPLY -> NEED_HELP (jawaban pengguna yang diperiksa)
CHECK_BUDDY / AWAITING_REPLY -> NO_RESPONSE (batas waktu)
NO_RESPONSE -> AWAITING_REPLY (teman meminta ulang)
NEED_HELP / NO_RESPONSE -> CLOSED (teman menandai tindak lanjut)
```

SAFE dan CLOSED menutup kejadian dan memulai cooldown. NEED_HELP dan NO_RESPONSE tidak ditutup otomatis. Status koneksi OFFLINE dihitung terpisah dari status kejadian. Monitoring yang dijeda hanya mencegah deteksi baru; kejadian aktif masih dapat dikonfirmasi.

Tidak adanya telemetri >3 detik membatalkan kandidat observasi/diam; >8 detik menandai perangkat offline. Detector tidak menggunakan ketiadaan data sebagai bukti diam. UI menonaktifkan aksi saat heartbeat detector tidak diterima selama 5 detik.

## Kontrak perintah

```json
{
  "command_id": "uuid_baru_per_klik",
  "action": "REQUEST_STATUS",
  "actor": "edge2",
  "event_id": "id_kejadian_dari_state",
  "sent_at_ms": 1790000000000
}
```

`REQUEST_STATUS` hanya dari buddy; `SAFE`/`NEED_HELP` hanya dari subject saat menunggu balasan; `ACKNOWLEDGE` hanya dari buddy untuk NEED_HELP/NO_RESPONSE; ARM/DISARM hanya dari dashboard. Receipt mengorelasikan `command_id`, `ok`, dan alasan penolakan. Tombol menunggu konfirmasi detector, bukan sekadar menganggap publish MQTT sebagai keberhasilan.

Pemeriksaan actor/topic menjaga konsistensi protokol, bukan autentikasi kriptografis. Broker publik memungkinkan pihak lain membaca dan mengirim topik yang sama. Gunakan ID acak untuk isolasi demo, atau broker privat dan ACL per perangkat jika memerlukan kontrol akses.
