# Content Generator Master

Jalankan web interface content generator secara otomatis — tanpa perlu buka terminal.

## Langkah otomatis (jalankan ini setiap kali skill dipanggil)

Ikuti langkah-langkah berikut secara berurutan menggunakan Bash tool:

### 1. Pastikan dependencies terinstall
```bash
cd /home/user/inventory-tracker/content-generator && pip install -q -r requirements.txt --ignore-installed 2>/dev/null || true
```

### 2. Cek apakah server sudah berjalan di port 5000
```bash
curl -s http://localhost:5000 > /dev/null 2>&1 && echo "RUNNING" || echo "NOT_RUNNING"
```

### 3. Jika server belum berjalan, jalankan di background
```bash
cd /home/user/inventory-tracker/content-generator && nohup python app.py > /tmp/content-gen.log 2>&1 &
sleep 2
```

### 4. Verifikasi server berhasil start
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000
```

### 5. Tampilkan hasil ke user

Setelah server berjalan, sampaikan kepada user:
- URL akses: **http://localhost:5000**
- Status server (berhasil/gagal)
- Jika ada error, tampilkan 10 baris terakhir dari `/tmp/content-gen.log`

---

## Fitur aplikasi

- **7 tipe konten**: YouTube Video, Instagram Reel, TikTok, Video Ads, Social Post, Blog Post, Email Marketing
- **Form dinamis**: variabel disesuaikan per tipe, diisi langsung dari laman
- **Video frames**: setiap scene menghasilkan pasangan **start frame + end frame** (gambar 1280×720)
- **5 visual styles**: `cinematic`, `modern`, `clean`, `colorful`, `dark`
- **Download frames**: simpan gambar per scene

## Troubleshooting

Jika port 5000 sudah dipakai:
```bash
kill $(lsof -t -i:5000) 2>/dev/null; sleep 1
cd /home/user/inventory-tracker/content-generator && nohup python app.py > /tmp/content-gen.log 2>&1 &
```

Jika ANTHROPIC_API_KEY belum ada di environment, minta user untuk menjalankan:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
lalu panggil `/content-generator-master` lagi.
