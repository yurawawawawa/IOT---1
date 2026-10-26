# Pengujian dan kalibrasi

## Uji otomatis

- Python: pengolahan data, sensor peak/rotasi, durasi diam kontinu, kedua peran, missing data, pergantian sesi, replay, timeout, hak peran, cooldown, kontrak MQTT, dan konfigurasi.
- JavaScript: kesamaan hasil fitur dengan Python dan ketersediaan tombol sesuai peran/status.
- Integrasi: broker MQTT lokal sungguhan, proses detector Python sungguhan, dua browser HP dan satu dashboard. Event sensor dibuat secara sintetis khusus pengujian. Hasilnya bukan bukti sensor HP fisik atau MQTT cloud.

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
| Jawaban tidak diberikan | NO RESPONSE setelah 30 detik | Belum diuji fisik |
| Permintaan belum dikirim | NO RESPONSE setelah 60 detik | Belum diuji fisik |
| WiFi salah satu HP dimatikan | OFFLINE; tidak dianggap diam | Belum diuji fisik |
| Tab dipindah / layar dikunci | Pesan sensor berhenti atau offline saat telemetri tidak tersedia | Belum diuji fisik |
| Detector dihentikan | UI mendeteksi detector offline dan tombol dinonaktifkan | Belum diuji fisik |
| Reconnect, refresh halaman | Telemetri pulih; kandidat sesi lama tidak diwariskan | Belum diuji fisik |

## Kalibrasi yang perlu dilakukan

1. Catat RMS, rotasi, dan peak ketika diam, berjalan, mengangkat HP, serta gerakan uji insiden terkontrol.
2. Ulangi setiap kondisi minimal 5 kali di masing-masing HP. Posisi HP harus konsisten dengan skenario penggunaan, misalnya saku atau digenggam.
3. Pilih ambang yang memisahkan gerakan biasa dari skenario uji. Ubah `.env`, restart detector, dan ulangi tes.
4. Jangan menurunkan ambang hanya supaya demo berhasil tanpa mencatat dampaknya pada alarm palsu.
5. Ukur waktu dari kejadian ke notifikasi, request ke prompt, dan jawaban ke tampilan teman. Laporkan kondisi jaringan saat mengukur.

Gunakan gerakan terkontrol tanpa menjatuhkan HP. Klaim hasil sebatas data yang benar-benar diukur; jika menggunakan simulasi, beri label simulasi.

## Alur video demo

1. Tampilkan kedua HP, dashboard laptop, dan jaringan yang sama.
2. Tunjukkan dua sensor valid dan angka fitur berubah sesuai gerakan.
3. Peragakan kejadian A -> notifikasi B -> request B -> jawaban SAFE dari A.
4. Balik peran dan peragakan NEED HELP dari B serta tindak lanjut A.
5. Tunjukkan timeout dan offline sebagai dua kondisi berbeda.
6. Jelaskan dua processing, algoritma temporal, MQTT cloud, dan alur konfirmasi dua arah BuddyCheck.
