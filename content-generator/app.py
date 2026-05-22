import re
import io
import os
import json
import base64
import textwrap

import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ── Content type definitions ──────────────────────────────────────────────────

CONTENT_TYPES = {
    "youtube_video": {
        "label": "YouTube Video",
        "icon": "🎬",
        "is_video": True,
        "variables": [
            {"name": "topic", "label": "Topik Video", "type": "textarea",
             "placeholder": "Contoh: Cara membuat kopi espresso sempurna di rumah"},
            {"name": "target_audience", "label": "Target Audience", "type": "text",
             "placeholder": "Contoh: Pecinta kopi usia 20-35 tahun"},
            {"name": "tone", "label": "Tone/Gaya", "type": "select",
             "options": ["Edukatif", "Menghibur", "Inspiratif", "Profesional", "Santai & Fun"]},
            {"name": "duration", "label": "Durasi Video", "type": "select",
             "options": ["1-3 menit", "5-10 menit", "10-15 menit", "15-30 menit"]},
            {"name": "cta", "label": "Call to Action", "type": "text",
             "placeholder": "Contoh: Subscribe dan aktifkan notifikasi"},
            {"name": "visual_style", "label": "Visual Style Frame", "type": "select",
             "options": ["cinematic", "modern", "clean", "colorful", "dark"]},
        ],
    },
    "instagram_reel": {
        "label": "Instagram Reel",
        "icon": "📱",
        "is_video": True,
        "variables": [
            {"name": "topic", "label": "Topik/Ide Konten", "type": "textarea",
             "placeholder": "Contoh: 5 tips produktivitas kerja dari rumah"},
            {"name": "niche", "label": "Niche/Kategori", "type": "text",
             "placeholder": "Contoh: Lifestyle, Bisnis, Fitness, Beauty"},
            {"name": "hook", "label": "Opening Hook", "type": "text",
             "placeholder": "Kalimat pembuka yang langsung menarik perhatian"},
            {"name": "duration", "label": "Durasi", "type": "select",
             "options": ["15 detik", "30 detik", "60 detik", "90 detik"]},
            {"name": "visual_style", "label": "Visual Style Frame", "type": "select",
             "options": ["modern", "cinematic", "clean", "colorful", "dark"]},
        ],
    },
    "tiktok": {
        "label": "TikTok Video",
        "icon": "🎵",
        "is_video": True,
        "variables": [
            {"name": "trend", "label": "Trend/Challenge/Sound", "type": "text",
             "placeholder": "Contoh: #POV #storytime atau nama sound trending"},
            {"name": "topic", "label": "Pesan/Topik Utama", "type": "textarea",
             "placeholder": "Apa yang ingin disampaikan dalam video ini"},
            {"name": "hook", "label": "Hook 3 Detik Pertama", "type": "text",
             "placeholder": "Visual/kalimat pembuka yang bikin orang berhenti scroll"},
            {"name": "target", "label": "Target Penonton", "type": "text",
             "placeholder": "Gen Z, Millennials, Ibu-ibu, dll"},
            {"name": "visual_style", "label": "Visual Style Frame", "type": "select",
             "options": ["modern", "colorful", "clean", "cinematic", "dark"]},
        ],
    },
    "video_ad": {
        "label": "Video Iklan/Ads",
        "icon": "📢",
        "is_video": True,
        "variables": [
            {"name": "product", "label": "Produk/Layanan", "type": "text",
             "placeholder": "Nama produk atau layanan yang dipromosikan"},
            {"name": "usp", "label": "Keunggulan Utama (USP)", "type": "textarea",
             "placeholder": "Apa yang membedakan produk/layanan Anda"},
            {"name": "target", "label": "Target Market", "type": "text",
             "placeholder": "Siapa target konsumen Anda"},
            {"name": "duration", "label": "Durasi Iklan", "type": "select",
             "options": ["15 detik", "30 detik", "60 detik"]},
            {"name": "emotion", "label": "Emosi yang Dibangkitkan", "type": "select",
             "options": ["Kepercayaan & Aman", "Kegembiraan & Excitement",
                         "FOMO/Urgensi", "Inspirasi", "Nostalgia", "Eksklusivitas"]},
            {"name": "visual_style", "label": "Visual Style Frame", "type": "select",
             "options": ["modern", "cinematic", "clean", "colorful", "dark"]},
        ],
    },
    "social_post": {
        "label": "Social Media Post",
        "icon": "✍️",
        "is_video": False,
        "variables": [
            {"name": "platform", "label": "Platform", "type": "select",
             "options": ["Instagram", "Twitter/X", "LinkedIn", "Facebook", "Threads"]},
            {"name": "topic", "label": "Topik/Pesan", "type": "textarea",
             "placeholder": "Apa yang ingin Anda posting dan sampaikan"},
            {"name": "tone", "label": "Tone", "type": "select",
             "options": ["Profesional", "Santai & Friendly", "Humoris",
                         "Inspiratif", "Informatif", "Emosional"]},
            {"name": "hashtags", "label": "Jumlah Hashtag", "type": "select",
             "options": ["Tidak ada", "3-5 hashtag", "5-10 hashtag", "10-20 hashtag"]},
        ],
    },
    "blog_post": {
        "label": "Blog Post / Artikel",
        "icon": "📝",
        "is_video": False,
        "variables": [
            {"name": "title", "label": "Judul/Topik Artikel", "type": "text",
             "placeholder": "Judul atau topik artikel yang ingin ditulis"},
            {"name": "keywords", "label": "Keyword SEO", "type": "text",
             "placeholder": "Kata kunci utama dan turunannya"},
            {"name": "length", "label": "Panjang Artikel", "type": "select",
             "options": ["500-800 kata", "1000-1200 kata", "1500-2000 kata", "2000+ kata"]},
            {"name": "tone", "label": "Gaya Penulisan", "type": "select",
             "options": ["Formal & Akademis", "Semi-formal",
                         "Casual & Conversational", "Storytelling", "How-to Guide"]},
            {"name": "audience", "label": "Target Pembaca", "type": "text",
             "placeholder": "Siapa yang akan membaca artikel ini"},
        ],
    },
    "email": {
        "label": "Email Marketing",
        "icon": "📧",
        "is_video": False,
        "variables": [
            {"name": "subject", "label": "Subjek/Tujuan Email", "type": "text",
             "placeholder": "Apa tujuan utama email ini"},
            {"name": "product", "label": "Produk/Layanan/Event", "type": "text",
             "placeholder": "Yang akan dipromosikan atau diinformasikan"},
            {"name": "offer", "label": "Penawaran/Value", "type": "text",
             "placeholder": "Diskon, free trial, bonus, informasi penting, dll"},
            {"name": "tone", "label": "Tone", "type": "select",
             "options": ["Formal & Profesional", "Friendly & Warm",
                         "Urgent & Compelling", "Exclusive & Premium"]},
            {"name": "cta", "label": "Call to Action", "type": "text",
             "placeholder": "Apa yang Anda ingin pembaca lakukan"},
        ],
    },
}

# ── Prompt builders ───────────────────────────────────────────────────────────

def _vars_text(variables):
    return "\n".join(f"- {k}: {v}" for k, v in variables.items() if v and str(v).strip())


def build_video_prompt(label, variables):
    return f"""Buat konten video {label} berkualitas tinggi berdasarkan spesifikasi berikut:

SPESIFIKASI:
{_vars_text(variables)}

Berikan HANYA output JSON valid (tanpa markdown code block, tanpa teks lain):
{{
  "title": "Judul konten yang menarik",
  "hook": "Opening hook 3-5 detik pertama yang langsung menarik",
  "scenes": [
    {{
      "id": 1,
      "time_range": "00:00-00:15",
      "visual_description": "Deskripsi visual scene",
      "narration": "Narasi/dialog yang diucapkan",
      "start_frame": "Deskripsi DETAIL opening frame scene: komposisi, pencahayaan, warna dominan, mood, objek/subjek utama, sudut kamera, gerakan akan terjadi",
      "end_frame": "Deskripsi DETAIL closing frame scene: perubahan komposisi, posisi final objek, perubahan cahaya/warna dari start frame"
    }}
  ],
  "full_script": "Script lengkap dengan time markers [00:00], [00:15], dll",
  "cta": "Call to action di akhir video",
  "caption": "Caption untuk posting di platform",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "video_start_frame": "Deskripsi SANGAT DETAIL opening frame seluruh video: setting, komposisi, pencahayaan, mood, warna, objek utama",
  "video_end_frame": "Deskripsi SANGAT DETAIL closing frame seluruh video: bagaimana video berakhir secara visual, pesan terakhir"
}}

Buat minimal 3-5 scenes. Setiap start_frame dan end_frame harus berbeda untuk menunjukkan perkembangan visual."""


def build_text_prompt(label, variables):
    return f"""Buat konten {label} berkualitas tinggi berdasarkan spesifikasi:

SPESIFIKASI:
{_vars_text(variables)}

Berikan HANYA output JSON valid (tanpa markdown code block):
{{
  "title": "Judul/tema konten",
  "main_content": "Konten lengkap siap posting",
  "alternative_1": "Versi alternatif pertama dengan pendekatan berbeda",
  "alternative_2": "Versi alternatif kedua yang lebih singkat",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "best_posting_time": "Waktu terbaik untuk posting konten ini",
  "engagement_tips": ["Tips meningkatkan engagement 1", "Tips 2", "Tips 3"],
  "hook_ideas": ["Hook alternatif 1", "Hook alternatif 2"]
}}"""


# ── Frame image generator ─────────────────────────────────────────────────────

_PALETTES = {
    "START": {
        "cinematic": [(8, 8, 24),    (16, 32, 72),   (24, 56, 104)],
        "modern":    [(12, 8, 28),   (32, 16, 80),   (72, 24, 120)],
        "clean":     [(235, 245, 255),(200, 225, 250),(160, 200, 240)],
        "colorful":  [(8, 24, 64),   (24, 80, 160),  (48, 140, 220)],
        "dark":      [(4, 4, 8),     (12, 16, 28),   (20, 28, 48)],
    },
    "END": {
        "cinematic": [(24, 8, 8),    (72, 20, 16),   (110, 36, 24)],
        "modern":    [(8, 24, 16),   (16, 80, 36),   (28, 120, 60)],
        "clean":     [(255, 248, 235),(255, 225, 200),(250, 200, 160)],
        "colorful":  [(64, 8, 24),   (160, 24, 80),  (220, 48, 130)],
        "dark":      [(8, 4, 4),     (24, 12, 8),    (44, 20, 12)],
    },
}


def _lerp(c1, c2, t):
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def _load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    if bold:
        candidates = [c for c in candidates if "Bold" in c] + \
                     [c for c in candidates if "Bold" not in c]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def create_frame_image(description, frame_type, style="cinematic",
                       title="", scene_num=None):
    W, H = 1280, 720
    is_start = (frame_type == "START FRAME")
    pk = "START" if is_start else "END"
    palette = _PALETTES[pk].get(style, _PALETTES[pk]["cinematic"])

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(H):
        t = y / (H - 1)
        c = _lerp(palette[0], palette[1], t * 2) if t < 0.5 \
            else _lerp(palette[1], palette[2], (t - 0.5) * 2)
        draw.line([(0, y), (W, y)], fill=c)

    # Geometric decoration
    if is_start:
        cx, cy = 200, H // 2
        for i in range(6):
            r = 40 + i * 70
            lum = max(12, 45 - i * 6)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         outline=(lum, lum + 18, lum + 44), width=2)
        # Play triangle
        draw.polygon([(cx - 26, cy - 36), (cx + 50, cy), (cx - 26, cy + 36)],
                     fill=(255, 210, 80))
    else:
        cx, cy = W - 200, H // 2
        for i in range(6):
            r = 40 + i * 70
            lum = max(12, 45 - i * 6)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         outline=(lum + 44, lum + 18, lum), width=2)
        # Finish circle + check
        draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(70, 190, 110))
        draw.line([(cx - 12, cy), (cx - 2, cy + 12), (cx + 14, cy - 12)],
                  fill=(255, 255, 255), width=3)

    # Top & bottom dark overlay
    img_rgba = img.convert("RGBA")
    for y in range(85):
        alpha = int(170 * (1 - y / 85))
        ov = Image.new("RGBA", (W, 1), (0, 0, 0, alpha))
        base = img_rgba.crop((0, y, W, y + 1))
        img_rgba.paste(Image.alpha_composite(base, ov), (0, y))
    for dy in range(210):
        y = H - 210 + dy
        alpha = int(200 * (dy / 210))
        ov = Image.new("RGBA", (W, 1), (0, 0, 0, alpha))
        base = img_rgba.crop((0, y, W, y + 1))
        img_rgba.paste(Image.alpha_composite(base, ov), (0, y))
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    f_badge = _load_font(16, bold=True)
    f_title = _load_font(24, bold=True)
    f_label = _load_font(11)
    f_desc  = _load_font(13)

    # Frame type badge
    badge_color = (35, 140, 65) if is_start else (180, 60, 30)
    bx, by = 24, 20
    bw = len(frame_type) * 9 + 28
    draw.rounded_rectangle([bx, by, bx + bw, by + 34], radius=6, fill=badge_color)
    draw.text((bx + 14, by + 8), frame_type, fill=(255, 255, 255), font=f_badge)

    if scene_num is not None:
        sx = bx + bw + 10
        draw.rounded_rectangle([sx, by, sx + 95, by + 34], radius=6, fill=(50, 50, 90))
        draw.text((sx + 10, by + 8), f"SCENE {scene_num}",
                  fill=(190, 190, 255), font=f_badge)

    if title:
        short = (title[:56] + "…") if len(title) > 56 else title
        draw.text((24, 64), short, fill=(255, 255, 255), font=f_title)

    # Description panel
    dy0 = H - 195
    draw.text((24, dy0), "SCENE DESCRIPTION", fill=(145, 145, 170), font=f_label)
    for i, line in enumerate(textwrap.wrap(description[:400], width=108)[:5]):
        draw.text((24, dy0 + 18 + i * 22), line, fill=(225, 225, 225), font=f_desc)

    draw.text((W - 190, H - 20), "Content Generator Pro",
              fill=(65, 65, 92), font=f_label)

    for t in range(2):
        draw.rectangle([t, t, W - 1 - t, H - 1 - t], outline=badge_color)

    return img


def _img_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/content-types")
def api_content_types():
    return jsonify(CONTENT_TYPES)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    ct_key    = data.get("content_type", "")
    variables = data.get("variables", {})

    if ct_key not in CONTENT_TYPES:
        return jsonify({"error": "Tipe konten tidak valid"}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY tidak ditemukan di environment"}), 500

    ct = CONTENT_TYPES[ct_key]
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=("Anda adalah content creator profesional. "
                                "Berikan output HANYA berupa JSON valid tanpa markdown code block.")
        )
        prompt = (build_video_prompt(ct["label"], variables)
                  if ct["is_video"]
                  else build_text_prompt(ct["label"], variables))

        resp = model.generate_content(prompt)
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            result = json.loads(m.group()) if m else {"raw_content": raw}

        return jsonify(result)

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/generate-frames", methods=["POST"])
def api_generate_frames():
    data         = request.get_json()
    frames_input = data.get("frames", [])
    style        = data.get("style", "cinematic")
    title        = data.get("title", "")

    if not frames_input:
        frames_input = [{
            "start_frame": data.get("start_frame_description", "Opening scene"),
            "end_frame":   data.get("end_frame_description",   "Closing scene"),
            "scene_num":   None,
        }]

    out = []
    for f in frames_input:
        s_desc = f.get("start_frame", "Opening frame")
        e_desc = f.get("end_frame",   "Closing frame")
        num    = f.get("scene_num")
        s_img  = create_frame_image(s_desc, "START FRAME", style, title, num)
        e_img  = create_frame_image(e_desc, "END FRAME",   style, title, num)
        out.append({
            "scene_num":         num,
            "start_frame":       _img_b64(s_img),
            "end_frame":         _img_b64(e_img),
            "start_description": s_desc,
            "end_description":   e_desc,
        })

    return jsonify({"frames": out})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
