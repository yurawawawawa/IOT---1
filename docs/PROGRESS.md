# Status pengerjaan

Tanggal mulai: 26 Oktober 2026.

## Implementasi tersedia

- [x] Modul BuddyCheck untuk sensor fisik, pemrosesan fitur, koneksi MQTT, dan server dashboard.
- [x] RMS gerakan, integrasi rotasi, dan peak percepatan.
- [x] Algoritma lonjakan + rotasi -> diam kontinu untuk kedua HP.
- [x] Check-in dua arah: request, SAFE, NEED_HELP, timeout, retry, tindak lanjut.
- [x] Status offline terpisah dari tidak menjawab.
- [x] Deduplikasi QoS 1, timestamp, validasi input, dan reset observasi saat data hilang.
- [x] UI HP dan dashboard responsif; sensor fisik browser; alternatif Termux.
- [x] Konfigurasi kelompok, script setup/run, README, arsitektur dan rencana uji.
- [x] 56 unit/integration test Python dan 8 test JavaScript lulus.
- [x] Pengujian integrasi broker MQTT lokal + detector Python: SAFE, NEED_HELP, timeout, retry, offline, dan jeda deteksi lulus. Input sensor sintetis.
- [x] Probe publish/subscribe cloud HiveMQ melalui MQTT/TLS port 8883 dan WSS port 8884 berhasil dari laptop pengembangan.
- [x] Paket `dist/buddycheck-web.zip` diverifikasi memuat halaman/aset/lisensi, tanpa `.env`.
- [x] Redesign hiking retro: ilustrasi pegunungan original hasil ImageGen, font lokal, palet forest/cream/orange, serta hero ringkas pada sesi HP aktif.
- [x] Notifikasi permintaan masuk: pola getar pada browser pendukung, bunyi, banner, tombol tes, dan fallback tanpa getar. Pemanggilan API dan alur notifikasi sudah diuji otomatis; respons getar/bunyi pada perangkat fisik masih perlu diverifikasi.
- [x] ID kelompok bebas: ruang dibuat otomatis dengan engine terpisah, JOIN/heartbeat browser, batas jumlah ruang, serta pembersihan ruang idle.
- [x] Uji integrasi dua ruang dengan ID berbeda dari `.env`: telemetri, kejadian, permintaan, dan balasan terisolasi; perintah lintas ruang ditolak.
- [x] Konflik peran sensor mengirim pesan ke sesi HP yang digantikan, dengan tombol Mulai tersedia kembali. Proses detector kedua tidak bisa memakai port dashboard yang sama.

## Tahap berikutnya bersama perangkat asli

- [x] Hosting folder web melalui HTTPS di Netlify.
- [x] Pembacaan sensor kedua HP terkonfirmasi dari uji pengguna.
- [x] Alur dasar dengan kedua HP dan detector laptop melalui MQTT cloud dikonfirmasi pengguna berjalan pada 27 Oktober 2026. Model perangkat, versi browser, dan metrik pengujian belum dicatat lengkap.
- [ ] Kalibrasi ambang dan isi matriks uji fisik.
- [x] Siapkan repository GitHub kelompok: https://github.com/yurawawawawa/IOT---1.
- [ ] PPT berdasarkan hasil nyata dan video demo.

Riwayat dan respons detector menggunakan memori; tidak dipersistensikan antar-restart. Screenshot dan uji otomatis menggunakan data uji sintetis, bukan rekaman pengujian fisik.
