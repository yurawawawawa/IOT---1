# Pengujian dan kalibrasi

## Uji otomatis

- Python: pengolahan data, sensor peak/rotasi, durasi diam kontinu, kedua peran, missing data, pergantian sesi, replay, timeout, hak peran, cooldown, kontrak MQTT, dan konfigurasi.
- JavaScript: kesamaan hasil fitur dengan Python dan ketersediaan tombol sesuai peran/status.
- Integrasi: broker MQTT lokal sungguhan, proses detector Python sungguhan, dua browser HP dan satu dashboard. Event sensor dibuat secara sintetis khusus pengujian. Hasilnya bukan bukti sensor HP fisik atau MQTT cloud.
- Ruang: ID bebas berbeda dari `.env`, dua ruang berjalan bersamaan, perintah lintas ruang ditolak, dan data/status tidak tercampur. Integrasi menggunakan dashboard kedua dan telemetri sintetis untuk ruang terpisah.

Perintah ada di README. Tes integrasi memperpendek durasi deteksi/timeout lewat environment agar pengujian cepat. Konfigurasi `.env` untuk pemakaian normal tidak diubah oleh tes.

## Matriks uji dua HP fisik — perlu diisi kelompok

Catat model/OS/browser kedua HP, posisi HP, tanggal uji, jaringan, broker, versi kode, dan konfigurasi ambang. Jalankan detector di laptop dan jangan menutup tab HP.

| Skenario | Harapan | Hasil aktual / bukti |
|---|---|---|
| Dua HP diam 30 detik | Sensor valid, 2/2 online, tidak ada kejadian | Belum diuji fisik |
| Kedua pengguna berjalan biasa | Tidak ada alarm yang tidak diperlukan | Belum diuji fisik |
| Rotasi tanpa lonjakan percepatan | Tidak membuka kejadian | Belum diuji fisik |
| Gerakan kuat lalu tetap bergerak | Kandidat berakhir tanpa check-in jika tidak diam cukup lama | Belum diuji fisik |
| A: lonjakan + rotasi, lalu diam | B menerima CHECK YOUR BUDDY | Belum diuji fisik |
| B meminta, A menjawab SAFE | Jawaban sampai ke B dan dashboard | Belum diuji fisik |
| B: kejadian, A meminta, B NEED HELP | Alur peran terbalik berhasil | Belum diuji fisik |
| Tekan Tes bunyi & getar pada Android | Bunyi pendek dan pola getar, jika didukung perangkat/browser | Belum diuji fisik |
| REQUEST STATUS masuk ke Android | Banner ARE YOU OK?, bunyi, dan pola getar tiga kali; tidak berulang setiap heartbeat | Belum diuji fisik |
| REQUEST STATUS masuk ke Safari iPhone | Banner dan bunyi setelah audio diaktifkan; tanpa getaran web | Belum diuji fisik |
| Jawaban tidak diberikan | NO RESPONSE setelah 30 detik | Belum diuji fisik |
| Permintaan belum dikirim | NO RESPONSE setelah 60 detik | Belum diuji fisik |
| WiFi salah satu HP dimatikan | OFFLINE; tidak dianggap diam | Belum diuji fisik |
| Tab dipindah / layar dikunci | Pesan sensor berhenti atau offline saat telemetri tidak tersedia | Belum diuji fisik |
| Detector dihentikan | UI mendeteksi detector offline dan tombol dinonaktifkan | Belum diuji fisik |
| Reconnect, refresh halaman | Telemetri pulih; kandidat sesi lama tidak diwariskan | Belum diuji fisik |
| Kedua HP memakai ID baru yang sama, berbeda dari `.env` | Detector membuat ruang otomatis; dashboard yang memilih ID itu menunjukkan 2/2 aktif | Belum diuji fisik |
| Kedua HP memakai ID berbeda | Setiap ruang hanya melihat HP miliknya; tidak terpasang sebagai satu pasangan | Belum diuji fisik |

## Mengatasi konflik sesi dan mengulang demo

Jika muncul **Sesi sensor lama sudah berakhir** atau **Sesi HP A/B digantikan sesi lain**, ada lebih dari satu sesi sensor yang memakai peran sama dalam satu kelompok. Tutup tab lama (termasuk browser dalam Instagram), lalu buka satu tab sensor saja pada setiap HP. Pilih **HP A** di HP pertama dan **HP B** di HP kedua dengan ID dan broker yang sama. Tekan Mulai lagi. Laptop yang hanya memantau harus memakai halaman **Dashboard**, bukan ikut menyalakan sensor HP A/B.

Jalankan hanya satu `run.bat`. `Ctrl+C` lalu `Y` memang menghentikan batch; setelah menjalankannya kembali, sesi HP yang masih aktif tetap bisa mengirim. Detector baru menolak pemakaian port dashboard yang sama oleh proses kedua. Pada web terbaru, sesi sensor yang telah digantikan otomatis berhenti dan menampilkan petunjuk untuk memilih peran; data sesi penggantinya tetap diterima.

Untuk memicu kejadian, beri satu gerakan uji terkontrol yang menghasilkan **peak ≥ 8 m/s²** dan **rotasi ≥ 0,35 rad** dalam satu jendela pembacaan, lalu letakkan HP tetap diam sekitar **6–7 detik**. Goyangan terus-menerus tidak memenuhi syarat diam. **REQUEST STATUS** muncul di HP temannya; setelah ditekan, HP yang mengalami kejadian baru menampilkan **I'M SAFE / NEED HELP**. Setelah SAFE, tunggu cooldown 15 detik sebelum menguji kejadian berikutnya.

## Kalibrasi yang perlu dilakukan

1. Catat RMS, rotasi, dan peak ketika diam, berjalan, mengangkat HP, serta gerakan uji insiden terkontrol.
2. Ulangi setiap kondisi minimal 5 kali di masing-masing HP. Posisi HP harus konsisten dengan skenario penggunaan, misalnya saku atau digenggam.
3. Pilih ambang yang memisahkan gerakan biasa dari skenario uji. Ubah `.env`, restart detector, dan ulangi tes.
4. Jangan menurunkan ambang hanya supaya demo berhasil tanpa mencatat dampaknya pada alarm palsu.
5. Ukur waktu dari kejadian ke notifikasi, request ke prompt, dan jawaban ke tampilan teman. Laporkan kondisi jaringan saat mengukur.

Gunakan gerakan terkontrol tanpa menjatuhkan HP. Klaim hasil sebatas data yang benar-benar diukur; jika menggunakan simulasi, beri label simulasi.

Untuk uji notifikasi, tekan **Tes bunyi & getar** sekali di masing-masing HP, lalu uji permintaan nyata dari temannya. Periksa volume HP jika bunyi tidak terdengar. Dukungan `navigator.vibrate()` tidak memastikan getaran terasa pada semua pengaturan perangkat, misalnya saat getaran dinonaktifkan oleh sistem. **Bisukan bunyi** hanya mematikan audio, sementara getar dan banner tetap tersedia sesuai dukungan browser. Notifikasi ini berjalan di halaman web aktif, bukan push notification saat aplikasi ditutup.

## Alur video demo

1. Tampilkan kedua HP, dashboard laptop, dan jaringan yang sama.
2. Tunjukkan dua sensor valid dan angka fitur berubah sesuai gerakan.
3. Peragakan kejadian A -> notifikasi B -> request B -> jawaban SAFE dari A.
4. Balik peran dan peragakan NEED HELP dari B serta tindak lanjut A.
5. Tunjukkan timeout dan offline sebagai dua kondisi berbeda.
6. Jelaskan dua processing, algoritma temporal, MQTT cloud, dan alur konfirmasi dua arah BuddyCheck.
