# Panduan menjalankan BuddyCheck

## Kebutuhan

- Laptop dengan Python **3.10+**, internet, dan browser.
- Dua HP yang memiliki **accelerometer dan gyroscope**, beserta browser yang mengekspos kedua sensor. Periksa perangkat terlebih dahulu; tidak semua HP memiliki gyro.
- Laptop dan kedua HP pada WiFi/hotspot yang sama untuk demo sesuai rubrik.
- Halaman sensor HP disajikan melalui **HTTPS**. HTTP alamat IP laptop cukup untuk dashboard, tetapi bukan untuk akses sensor HP.
- Broker MQTT cloud dengan endpoint TLS untuk Python dan WSS untuk browser. Default konfigurasi menggunakan broker publik HiveMQ.

Node.js hanya diperlukan untuk pengembangan/pengujian JavaScript. Halaman web sudah menyertakan MQTT.js lokal; tidak membutuhkan npm atau proses build untuk digunakan.

Tampilan menggunakan tema hiking retro dengan ilustrasi pegunungan khusus BuddyCheck, palet forest/cream/orange, serta font lokal. Aset dan prompt pembuatannya ada di [catatan desain](design/ASSETS.md).

## 1. Jalankan di laptop Windows

Cara cepat: jalankan `setup.bat` sekali, lalu `run.bat`.

Atau melalui PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\setup_env.py
.\.venv\Scripts\python.exe detector.py
```

Buka **http://localhost:8000/?view=dashboard**. ID awal dan URL broker diisi dari konfigurasi laptop. Ganti ID dengan ruang yang digunakan kedua HP jika berbeda, klik **Hubungkan dashboard**, dan tunggu **Detector aktif**.

`scripts/setup_env.py` membuat `.env` dengan ID awal dashboard dan tidak menimpa konfigurasi yang sudah ada. Kedua HP boleh membuat ID lain secara langsung di halaman HP Edge; tidak perlu mengubah `.env` atau restart detector untuk mengganti ruang. ID harus sama persis, 1–80 karakter berupa huruf ASCII, angka, `_`, atau `-`, dan bersifat case-sensitive. Perubahan broker atau ambang deteksi tetap memerlukan edit `.env` dan restart detector.

Dashboard di jaringan yang sama bisa dibuka melalui `http://IP_LAPTOP:8000/?view=dashboard`. Temukan IPv4 WiFi laptop menggunakan `ipconfig`. Bila diblokir, izinkan Python pada jaringan privat di Windows Firewall. Jangan gunakan URL HTTP ini untuk sensor HP.

## 2. Buka halaman sensor di dua HP

Upload **seluruh isi folder `web/`**, termasuk `vendor/`, ke hosting statis HTTPS milik kelompok. Contoh cara manual: masukkan folder `web` ke layanan deploy statis seperti Netlify Drop. Hosting belum dibuat oleh proyek ini; URL di bawah adalah placeholder.

Jika Netlify Drop menampilkan kegagalan build pada halaman Agent runs, buka Project overview dan pilih folder pada bagian Already built it. Upload folder `web` langsung. Folder ini menyertakan `netlify.toml` dengan publish directory `.` dan perintah build sederhana karena BuddyCheck sudah berupa file statis. `exit code 2` saja belum menjelaskan akar kegagalan; periksa Deploy log bila masih gagal.

Paket siap upload juga dapat dibuat dengan `.\.venv\Scripts\python.exe -m scripts.package_web`, menghasilkan `dist/buddycheck-web.zip` dengan `index.html` di akar arsip. Paket ini hanya berisi aset web dan lisensi, tanpa `.env`.

```text
https://HOSTING-KELOMPOK/?view=phone&role=edge1
https://HOSTING-KELOMPOK/?view=phone&role=edge2
```

Di HP A:

1. Pilih **HP A — Pengguna pertama**.
2. Buat ID kelompok, misalnya `pendaki_07`. ID ini boleh berbeda dari ID awal detector.
3. Samakan URL WSS dengan `MQTT_WS_URL` di `.env`.
4. Klik **Mulai sensor & hubungkan** dan izinkan sensor gerak jika diminta.

Ulangi di HP B dengan peran **HP B — Pengguna kedua**. Peran harus berbeda. Pastikan angka sampel accelerometer dan gyroscope bertambah di kedua HP dan dashboard menunjukkan **2/2 perangkat aktif**.

Gunakan ID dan broker yang sama di kedua HP. Pada dashboard, pilih ID tersebut untuk melihat aktivitasnya. Room dibuat otomatis saat perangkat bergabung atau mengirim telemetri; data, kejadian, cooldown, dan perintah dari ID lain disimpan terpisah. Satu detector melayani maksimal 32 ruang aktif. Ruang tanpa pesan masuk selama 15 menit dibersihkan; halaman baru mengirim JOIN berkala selama terhubung.

Pada panel **Konfirmasi kondisi**, tekan **Tes bunyi & getar** untuk mengaktifkan audio dari interaksi langsung dan memeriksa notifikasi di masing-masing HP. Permintaan status masuk menghasilkan pola getar tiga kali pada browser yang mendukungnya, tiga bunyi pendek, serta banner **ARE YOU OK?** dengan tombol untuk membuka kartu permintaan. Safari iPhone menggunakan bunyi dan banner karena getaran web tidak tersedia. Periksa volume HP dan pertahankan layar/tab tetap aktif.

Pertahankan layar dan tab browser tetap aktif. Browser dapat menghentikan sensor saat layar terkunci atau aplikasi dipindah ke latar belakang. Halaman tidak membuat data pengganti ketika sensor tidak tersedia. [Referensi izin sensor](https://developer.mozilla.org/en-US/docs/Web/API/DeviceMotionEvent/requestPermission_static).

Broker privat: isi kredensial Python di `.env`; masukkan kredensial klien browser secara manual pada bagian **Broker dengan akun**. Password server tidak dikirim melalui `/config.json` atau disimpan ke local storage.

## 3. Coba alur BuddyCheck

1. Amati data kedua HP saat diam dan bergerak biasa. Tidak semestinya ada kejadian.
2. Pada HP A, buat gerakan terkontrol yang menghasilkan lonjakan percepatan sekaligus rotasi, kemudian letakkan diam. **Tidak perlu menjatuhkan HP.** Amati nilai peak/rotasi untuk mengetahui apakah ambang tercapai.
3. Jika kedua ambang tercapai, status A menjadi **Observasi**. Setelah data diam berkelanjutan selama 5 detik, B menerima **CHECK YOUR BUDDY**.
4. Di HP B tekan **REQUEST STATUS**.
5. HP A menampilkan **ARE YOU OK?**, dengan tombol **I'M SAFE** dan **NEED HELP**.
6. Pilih jawaban di A; status yang sama tampil di B dan dashboard.
7. Ulangi dengan peran terbalik: kejadian pada B, permintaan dari A, jawaban dari B.

Jika belum ada permintaan setelah 60 detik atau jawaban belum diterima 30 detik setelah permintaan, status menjadi **NO RESPONSE**. Teman dapat meminta status ulang atau menandai sudah ditindaklanjuti. **NEED HELP** tetap aktif sampai teman menandai tindak lanjut. Jawaban **SAFE** menutup kejadian dan memulai cooldown 15 detik.

**OFFLINE** berarti tidak ada telemetri valid selama 8 detik. Ini berbeda dari **NO RESPONSE**, yang berarti belum ada konfirmasi pengguna. Data sensor hilang tidak dihitung sebagai kondisi diam.

## Pemrosesan dan algoritma

| Komponen | Implementasi |
|---|---|
| Edge fisik | HP A dan HP B; keduanya mengolah dan mengirim data sensor |
| Sensor | Accelerometer + gyroscope pada masing-masing HP |
| Processing 1 | RMS dari `sqrt(ax² + ay² + az²) − 9.81` |
| Processing 2 | Integrasi `sqrt(gx² + gy² + gz²) × Δt` menghasilkan total rotasi |
| Fitur tambahan | Puncak absolut deviasi magnitudo percepatan dalam jendela |
| Jendela browser | Sekitar 1 detik, sampling dibatasi sekitar 20 Hz; minimal 4 sampel |
| Algoritma | Lonjakan peak ≥8 m/s² **dan** rotasi ≥0.35 rad; kemudian RMS ≤0.6 dan rotasi ≤0.15 selama ≥5 detik, dalam observasi maksimal 12 detik |
| Komunikasi | MQTT QoS 1 melalui TLS/WSS ke broker cloud |
| Dashboard | Server Python lokal di jaringan yang sama; subscribes ke state melalui MQTT |

Gyroscope browser memberikan derajat/detik dan dikonversi menjadi radian/detik sebelum integrasi. Total rotasi adalah akumulasi gerakan sudut, bukan sudut orientasi akhir. [Referensi satuan browser](https://developer.mozilla.org/en-US/docs/Web/API/DeviceMotionEvent/rotationRate).

Nilai awal ini perlu dikalibrasi sesuai HP, posisi HP, dan aktivitas. Prototipe mendeteksi pola gerakan **HP**; pola tersebut tidak membuktikan pengguna jatuh. Permintaan dan jawaban pengguna adalah bagian konfirmasi kondisinya.

## Pengujian software

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/core.test.cjs
.\.venv\Scripts\python.exe -m scripts.offline_demo
```

Tes integrasi lengkap (memakai broker lokal dan **event sensor sintetis**):

```powershell
npm.cmd ci
npx.cmd playwright install chromium
npm.cmd run test:integration
```

Tes membuka dua halaman HP dan dua dashboard untuk ruang berbeda, menjalankan detector Python, dan memeriksa alur aman, perlu bantuan, timeout, offline, jeda deteksi, serta isolasi antar-ID. ID pengujian berbeda dari nilai awal `.env`. Tidak mengirim data uji ke broker publik. Screenshot pengujian tersimpan di `test-results/` dan diabaikan Git.

Saat server lokal berjalan, `npm.cmd run test:visual` memeriksa aset, error browser, dan lebar halaman pada desktop, tablet, serta dua ukuran HP. Screenshot berada di `test-results/hiking-*.png`.

Untuk memeriksa koneksi laptop ke broker cloud yang dikonfigurasi: `.\.venv\Scripts\python.exe -m scripts.check_cloud`. Script menguji publish/subscribe melalui MQTT/TLS dan WSS memakai topik diagnostik acak serta probe teks; tidak mengirim data sensor.

Lihat [rencana uji fisik](TESTING.md), [arsitektur dan kontrak MQTT](ARCHITECTURE.md), serta [catatan pengerjaan](PROGRESS.md).

## Alternatif Android: Termux

Jika browser tidak mengekspos sensor tetapi HP memiliki kedua sensor fisik, gunakan Termux + Termux:API. Di Termux pasang `python`, `git`, dan `termux-api`, install `requirements.txt`, lalu set `PROJECT_ID` pada masing-masing HP ke ID ruang yang sama dan samakan konfigurasi brokernya. ID awal pada laptop boleh berbeda.

```sh
python edge.py --device edge1
# Di HP lainnya:
python edge.py --device edge2
```

Terminal mencetak ID kejadian. Gunakan `request EVENT_ID`, `safe EVENT_ID`, `help EVENT_ID`, atau `done EVENT_ID` sesuai peran. Jalur ini membaca sensor fisik secara default. Jangan jalankan browser dan Termux bersamaan untuk peran perangkat yang sama.

Untuk latihan software saja: `python edge.py --device edge1 --source simulator --scenario incident`. Source **SIMULASI** ditandai di telemetri dan UI. Ini tidak memenuhi bukti demo dua HP fisik.

## Struktur proyek

```text
detector.py             Entry point laptop: dashboard + MQTT detector
buddycheck.py           Algoritma temporal dan state machine dua arah
service.py              Adapter MQTT, heartbeat, receipt perintah
edge.py                Alternatif sensor Android melalui Termux
shared/                Pemrosesan, sensor, pesan, koneksi, server web
web/                   Halaman HP/dashboard statis, siap hosting HTTPS
tests/                 Unit tests dan integrasi browser/broker lokal
docs/                  Arsitektur, rencana uji, status pengerjaan
scripts/               Setup konfigurasi, simulasi offline, vendor MQTT.js
```

Riwayat kejadian disimpan di memori detector (maksimal 50), bukan database. Restart detector memulai sesi baru. Semua perangkat perlu jam yang tersinkron. Broker publik tidak menyediakan privasi atau autentikasi identitas pengirim; ID kelompok memisahkan topik, bukan menjadi password. Gunakan broker privat dan ACL untuk penggunaan di luar demo kelas.

Lisensi dan atribusi: [LICENSE](../LICENSE), [NOTICE.md](../NOTICE.md).
