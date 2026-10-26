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
- [x] 40 unit/integration test Python dan 5 test JavaScript lulus.
- [x] Pengujian integrasi broker MQTT lokal + detector Python + tiga konteks browser: SAFE, NEED_HELP, timeout, retry, offline, dan jeda deteksi lulus. Input sensor sintetis.
- [x] Probe publish/subscribe cloud HiveMQ melalui MQTT/TLS port 8883 dan WSS port 8884 berhasil dari laptop pengembangan.
- [x] Paket `dist/buddycheck-web.zip` diverifikasi memuat halaman/aset/lisensi, tanpa `.env`.
- [x] Redesign hiking retro: ilustrasi pegunungan original hasil ImageGen, font lokal, palet forest/cream/orange, serta hero ringkas pada sesi HP aktif.

## Tahap berikutnya bersama perangkat asli

- [ ] Hosting folder web melalui HTTPS milik kelompok.
- [ ] Konfirmasi dua HP memiliki sensor dan browser mengeksposnya.
- [ ] Uji MQTT cloud dengan kedua HP dan laptop pada WiFi/hotspot yang sama.
- [ ] Kalibrasi ambang dan isi matriks uji fisik.
- [x] Siapkan repository GitHub kelompok: https://github.com/yurawawawawa/IOT---1.
- [ ] PPT berdasarkan hasil nyata dan video demo.

Riwayat dan respons detector menggunakan memori; tidak dipersistensikan antar-restart. Screenshot dan uji otomatis menggunakan data uji sintetis, bukan rekaman pengujian fisik.
