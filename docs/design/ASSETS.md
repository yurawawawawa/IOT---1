# BuddyCheck hiking visual direction

Palet: forest green, parchment cream, burnt orange, dan sage. Tipografi display Anton; teks antarmuka DM Sans. Ilustrasi dibuat khusus untuk BuddyCheck dengan komposisi baru, dua pendaki dan pegunungan vulkanik; referensi pengguna dipakai sebagai arah suasana retro outdoors.

## Aset ilustrasi

- Mode: built-in ImageGen (`image_gen.imagegen`), generasi gambar baru.
- Master: `docs/design/hiking-hero-source.png` (1536 × 1024).
- Aset web: `web/assets/hiking-hero.webp` (1536 × 1024, kualitas 87; sekitar 360 KB).
- Konversi PNG ke WebP hanya mengoptimalkan format, tanpa perubahan isi ilustrasi.
- Semua teks UI tetap berupa HTML, tidak tertanam dalam gambar.

## Prompt final

```text
Use case: illustration-story. Asset type: original wide illustrated hero background for BuddyCheck, an Indonesian two-person hiking activity and buddy check-in web app. Create a premium vintage outdoor travel-poster landscape, horizontal 3:2 composition. Flat cut-paper shapes, subtle risograph and screen-print grain, bold simplified silhouettes, sophisticated editorial illustration. A distinctive Indonesian volcanic mountain ridge in the distance, winding ochre walking trail through layered forest and meadow, rounded pine and tropical hillside foliage, a small pale apricot rising sun. Two small hikers, one with a burnt-orange backpack and one with a cream backpack, walking together in the lower right third, wearing outdoor hats and carrying trekking poles; believable lively silhouettes, not geometric stick figures. Deep forest green #233d32 dominant, sage and moss greens, warm parchment #f2e8c9, burnt orange #ef9650, subtle muted teal. IMPORTANT: the upper 35 percent is quiet deep green sky and distant layered ridges, dark enough to place large cream website lettering over it later in HTML; keep all people and main visual interest below that area. Wide scenic panorama with generous breathing room. Nature is lush and graphic, not photographic, no gradients or 3D gloss. This should feel like its own original hiking expedition poster, not a copy of an existing hiking club poster or any beverage brand. No text, no typography, no letters, no logo, no border, no watermark.
```

## Font

- Anton: https://github.com/google/fonts/tree/main/ofl/anton
- DM Sans: https://github.com/google/fonts/tree/main/ofl/dmsans
- Font disajikan dari folder `web/fonts/` agar tidak bergantung pada layanan font eksternal saat halaman dibuka. Pemberitahuan SIL OFL berada di folder yang sama.

## Penyesuaian layar HP

Ilustrasi penuh tampil sebelum sesi dimulai. Sesudah sensor diaktifkan, hero dipadatkan pada layar kecil agar panel kejadian dan tombol konfirmasi mudah dijangkau. Warna peringatan dan status koneksi mengikuti data aktual; tidak ada data lokasi atau rute yang direkayasa untuk dekorasi.
