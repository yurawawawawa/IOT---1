# BuddyCheck

**Teman di setiap langkah.** Proyek mata kuliah Internet of Things untuk memantau aktivitas dua pengguna dan melakukan konfirmasi kondisi dua arah melalui cloud.

<img src="web/assets/hiking-hero.webp" alt="Ilustrasi dua pendaki di jalur pegunungan — BuddyCheck" width="760">

Saat beraktivitas bersama, gerakan tidak biasa pada salah satu pengguna bisa luput dari perhatian temannya. BuddyCheck membaca sensor pada dua HP, mendeteksi pola gerakan yang perlu diperiksa, lalu meminta pengguna saling mengonfirmasi kondisi.

## Sesuai ketentuan tugas

| Ketentuan | Implementasi BuddyCheck |
|---|---|
| Minimal 2 edge device | Dua HP fisik: HP A dan HP B |
| Minimal 2 sensor | Accelerometer dan gyroscope pada masing-masing HP |
| Minimal 2 data processing | RMS gerakan dari accelerometer dan total rotasi dari gyroscope |
| Algoritma pengolahan | Algoritma berbasis aturan: lonjakan percepatan + rotasi, dilanjutkan kondisi diam |
| Komunikasi ke cloud | MQTT melalui TLS/WSS ke broker cloud |
| Dashboard | Dashboard laptop pada jaringan yang sama dengan kedua HP |
| Komunikasi dua arah | Permintaan status, jawaban aman/perlu bantuan, dan tindak lanjut |

Kedua HP memiliki peran setara: A dapat memeriksa B, dan B dapat memeriksa A.

**ID kelompok bebas dibuat pengguna**, misalnya `pendaki_07` atau `jalanbareng123`. Kedua HP terhubung ke ruang yang sama jika ID dan brokernya sama, dengan peran A/B berbeda. Detector membuat ruang otomatis; `PROJECT_ID` di `.env` hanya ID awal dashboard. Masukkan ID ruang yang sama di dashboard untuk memantaunya.

## Cara kerja

```text
HP A ──┐                        ┌── Detector Python di laptop
       ├── MQTT broker cloud ────┤
HP B ──┘                        └── Dashboard laptop
```

Masing-masing HP mengolah sensor menjadi RMS gerakan, total rotasi, dan puncak percepatan. Hasilnya dikirim ke cloud dan dianalisis oleh detector. Permintaan status serta balasan pengguna juga melewati broker yang sama.

Alur konfirmasi saat kejadian terdeteksi pada A:

```text
A: gerakan tidak biasa → diam beberapa detik
                    ↓
B: CHECK YOUR BUDDY → tekan REQUEST STATUS
                    ↓
A: ARE YOU OK? → pilih I'M SAFE atau NEED HELP
                    ↓
B dan dashboard menerima hasil konfirmasi
```

**Dashboard** menampilkan aktivitas kedua HP dan mengatur jeda deteksi. **HP Edge** membaca sensor serta menyediakan tombol permintaan dan jawaban status. Detector Python tetap harus berjalan di laptop.

Saat permintaan status masuk, HP penerima mendapat pola getar tiga kali pada browser yang mendukungnya, tiga bunyi pendek, dan banner **ARE YOU OK?**. Tombol **Tes bunyi & getar** tersedia di panel Konfirmasi kondisi. Safari iPhone tidak menyediakan getaran web; gunakan bunyi dan tampilan visual. Layar serta tab harus tetap aktif, dan bunyi dapat dibisukan melalui tombol di panel yang sama.

## Menjalankan proyek

Siapkan Python **3.10+**, laptop, dua HP dengan accelerometer dan gyroscope, serta internet. Untuk demo, sambungkan ketiga perangkat ke WiFi/hotspot yang sama.

### 1. Laptop

```powershell
git clone https://github.com/yurawawawawa/IOT---1.git
cd IOT---1
.\setup.bat
.\run.bat
```

`setup.bat` memasang dependensi dan membuat `.env` dengan ID awal dashboard. `run.bat` menjalankan detector untuk semua ruang dan server dashboard. Biarkan terminalnya terbuka selama pengujian.

Buka [dashboard lokal](http://localhost:8000/?view=dashboard), klik **Hubungkan dashboard**, dan tunggu **Detector aktif**.

### 2. Kedua HP

1. Upload folder **`web/`** beserta seluruh isinya ke hosting statis **HTTPS** milik kelompok.
2. Buka link hosting di kedua HP, lalu pilih **HP Edge**.
3. Pilih peran **HP A** di HP pertama dan **HP B** di HP kedua.
4. Buat ID kelompok yang sama di kedua HP, lalu samakan URL broker dengan `MQTT_WS_URL`. ID boleh berbeda dari `.env`.
5. Klik **Mulai sensor & hubungkan**, lalu izinkan sensor gerak.

Di dashboard, masukkan ID yang digunakan kedua HP lalu hubungkan. Pastikan sampel accelerometer dan gyroscope bertambah, serta dashboard menunjukkan **2/2 perangkat aktif**. Pertahankan layar dan tab browser tetap terbuka. Halaman sensor HP memerlukan HTTPS; alamat HTTP laptop digunakan untuk dashboard.

Paket hosting dapat dibuat dengan:

```powershell
.\.venv\Scripts\python.exe -m scripts.package_web
```

Hasilnya: `dist/buddycheck-web.zip`. Panduan setup manual, koneksi jaringan, dan alternatif Termux tersedia di [docs/SETUP.md](docs/SETUP.md).

## Demo dan pengujian

| Skenario | Hasil yang diharapkan |
|---|---|
| Dua HP diam atau bergerak biasa | Tidak membuka kejadian jika pola deteksi tidak terpenuhi |
| A mengalami lonjakan + rotasi, kemudian diam | B menerima **CHECK YOUR BUDDY** |
| B meminta status, A menjawab aman | **I'M SAFE** tampil di B dan dashboard |
| Peran dibalik, B meminta bantuan | A menerima **NEED HELP** |
| Pengguna tidak menjawab sampai batas waktu | **NO RESPONSE** |
| Telemetri salah satu HP berhenti | Perangkat ditandai **OFFLINE** |

Ambang awal di `.env`: peak **8 m/s²**, rotasi **0,35 rad**, lalu diam **5 detik**. Batas jawaban **30 detik**; perangkat offline setelah **8 detik** tanpa telemetri. Nilai tersebut perlu dikalibrasi pada kedua HP. Gunakan gerakan terkontrol tanpa menjatuhkan HP.

Tes software:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/core.test.cjs
```

Tes integrasi browser, broker MQTT lokal, dan detector:

```powershell
npm.cmd ci
npx.cmd playwright install chromium
npm.cmd run test:integration
```

Node.js **20+** hanya diperlukan untuk pengujian JavaScript dan integrasi. Halaman HP dan dashboard tidak memerlukan proses build.

Pengujian otomatis menggunakan data sintetis dan tidak menggantikan demo dua HP fisik. Matriks uji fisik dan panduan kalibrasi tersedia di [docs/TESTING.md](docs/TESTING.md).

## Struktur singkat

```text
detector.py       Menjalankan detector dan server dashboard
buddycheck.py     Algoritma deteksi dan alur konfirmasi
service.py        Pertukaran pesan MQTT
shared/          Sensor, pemrosesan fitur, dan konfigurasi
web/             Halaman HP Edge dan dashboard
tests/           Pengujian otomatis
docs/            Panduan, arsitektur, dan pengujian
```

Untuk pengumpulan, sertakan link repository ini dalam PPT beserta masalah, ide, arsitektur, sensor, processing, algoritma, cloud, dan hasil pengujian. Lengkapi dengan video demo sesuai ketentuan tugas.

Prototipe ini membaca pola gerakan HP untuk memicu pengecekan; kondisi pengguna dikonfirmasi melalui jawabannya. Riwayat kejadian disimpan di memori dan dimulai ulang saat detector direstart. Broker publik dipakai bersama, sehingga jangan mengirim data pribadi atau memasukkan `.env` ke Git.

[Arsitektur](docs/ARCHITECTURE.md) · [Lisensi](LICENSE) · [Dependensi](NOTICE.md)
