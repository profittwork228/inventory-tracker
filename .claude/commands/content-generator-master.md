# Content Generator Master

Web interface untuk membuat konten AI-powered. Setiap penggunaan akan membuka laman form interaktif di browser.

## Jalankan

```bash
cd content-generator
pip install -r requirements.txt
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python app.py
```

Buka **http://localhost:5000** di browser.

## Fitur

- **7 tipe konten**: YouTube Video, Instagram Reel, TikTok, Video Ads, Social Post, Blog Post, Email Marketing  
- **Form dinamis**: variabel disesuaikan per tipe, diisi langsung dari laman
- **Video frames**: setiap scene menghasilkan pasangan **start frame + end frame** (gambar 1280×720)
- **5 visual styles**: `cinematic`, `modern`, `clean`, `colorful`, `dark`
- **Download frames**: simpan gambar per scene

## Struktur output video

Setiap konten video menghasilkan:
1. Hook pembuka
2. Scene list (dengan deskripsi start frame & end frame per scene)
3. Full script bermarkah waktu
4. Caption + hashtag + CTA
5. Gambar **START FRAME** (biru/gelap, ikon play) & **END FRAME** (merah/oranye, ikon centang) per scene
