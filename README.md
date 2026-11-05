# Blogger Auto-Pilot & Multi-Blog Dashboard 🚀

Sistem manajemen konten otomatis, multi-akun, dan multi-blog untuk **Google Blogger (Blogspot)** yang dilengkapi dengan **Autonomous SEO Specialist Agent**, editor visual interaktif, optimasi gambar WebP, dan integrasi penuh Google Blogger API v3.

---

## ✨ Fitur Utama

1. **Multi-Account & Multi-Blog Switcher:**
   - Kelola banyak blog dan beberapa akun Google terpisah dalam satu dashboard.
   - Switch blog aktif secara instan dengan isolasi artikel dan keyword per-blog.
2. **Visual Editor & Readability Suite:**
   - Live preview HTML dengan kalkulasi jumlah kata real-time dan estimasi menit membaca.
   - Filter & pembersih script otomatis untuk menjaga integritas tampilan.
3. **Image SEO Suite & WebP Converter:**
   - Upload media lokal otomatis dikompres dan dikonversi ke format efisien `.webp`.
   - Pengisian Alt Text SEO otomatis untuk kepatuhan Google E-E-A-T.
4. **Autonomous SEO Auto-Draft Engine:**
   - Riset keyword terarah dan pembuatan draf artikel secara mandiri.
   - Tombol *"Jalankan Auto-Draft Sekarang"* langsung dari Web Dashboard.
   - Dapat dijalankan via cron otomatis (Hermes Agent / crontab Linux).
5. **One-Click Publish to Google Blogger:**
   - Review dan edit sebelum publish, atau simpan sebagai draft online di Blogger.

---

## 🛠️ Prasyarat & Persiapan Awal

### 1. Kebutuhan Sistem
- Python 3.10 atau versi lebih baru.
- Paket `uv` atau `pip` / `virtualenv`.

### 2. Kredensial Google Cloud Console (OAuth 2.0)
1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat proyek baru (misal: `Blogger-Automation`).
3. Aktifkan **Blogger API v3** di menu **APIs & Services → Library**.
4. Buka **APIs & Services → Credentials → Create Credentials → OAuth Client ID**:
   - **Application Type:** `Desktop App`
   - **Name:** `Blogger Agent Client`
5. Unduh file kredensial JSON dan simpan di folder ini dengan nama:
   ```bash
   client_secret.json
   ```

---

## 📦 Panduan Instalasi dari Nol

### Langkah 1: Clone Repositori
```bash
git clone <URL_REPO_ANDA> blogger-agent
cd blogger-agent
```

### Langkah 2: Buat Lingkungan Virtual & Install Dependensi
**Menggunakan `uv` (Direkomendasikan):**
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

*Atau menggunakan Python standar:*
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Langkah 3: Diagnosa Kesiapan SaaS
Periksa status konfigurasi database, kunci enkripsi AES, Midtrans payment gateway, dan Google OAuth:
```bash
python check_saas_readiness.py
```

### Langkah 4: Hubungkan Akun Google Blogger (1-Click OAuth)
Database terinisialisasi secara otomatis saat server berjalan. Untuk menghubungkan akun Google Blogger:
1. Buka dashboard di browser: `http://localhost:8090`
2. Klik tombol **"Hubungkan Akun Google"**
3. Berikan izin akses Google Blogger pada pop-up consent Google
4. Token akan dienkripsi dengan standar AES-256 dan disimpan secara aman di database tenant

---

## 🚀 Menjalankan Aplikasi

### Menjalankan Web Dashboard
```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8090
```
Buka di browser: **`http://localhost:8090`**

### Menjalankan Autopilot Background Scheduler (Daemon)
```bash
python autopilot_scheduler.py
```

---

## 📁 Struktur Direktori

```text
blogger-autopilot/
├── app.py                     # Entrypoint FastAPI & static mounts
├── routers/                   # Domain API Routers (auth, billing, blogs, articles, keywords, settings, admin)
├── content_generator.py       # Deep Module peracik artikel & BaseLLMAdapter seam
├── blogger_client.py          # Seam Blogger API v3 (Live & InMemory adapters)
├── midtrans_service.py        # Seam Midtrans Payment Gateway (Live & InMemory adapters)
├── notification_service.py    # Seam Notifikasi Telegram & Webhook (Live & InMemory adapters)
├── db_saas.py                 # Engine persistensi SQLAlchemy multi-tenant
├── models_saas.py             # Model relational User, Subscription, Blog, Article, Keyword
├── auth_saas.py               # Otentikasi tenant JWT, Bcrypt, & HttpOnly cookies
├── crypto_service.py          # Enkripsi & dekripsi token OAuth AES-256
├── autopilot_scheduler.py     # Background scheduler daemon siklus konten otonom
├── templates/index.html       # Authoritative Single Page Application Dashboard
├── seo_knowledge.md           # Basis pengetahuan SEO E-E-A-T
├── seo_master_prompt.md       # Prompt standar penulisan artikel
├── requirements.txt           # Dependensi Python
├── .env.example               # Template environment variables
└── uploads/                   # Media gambar WebP
```
