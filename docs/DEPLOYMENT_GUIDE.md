# 🚀 Panduan Deployment Cloud & Setup Produksi: Blogger Auto-Pilot SaaS

Panduan komprehensif ini menjelaskan langkah demi langkah cara men-deploy **Blogger Auto-Pilot** sebagai platform SaaS komersial multi-tenant siap rilis di cloud publik menggunakan **Supabase (PostgreSQL)**, **Midtrans Payment Gateway (QRIS & VA)**, dan **Docker**.

---

## 📋 Daftar Kebutuhan Eksternal (Prerequisites)

| Layanan | Fungsi | Status / Biaya |
| :--- | :--- | :--- |
| **Supabase** | Managed PostgreSQL + Row-Level Security (RLS) | Gratis (Free Tier 500MB) |
| **Midtrans** | Pembayaran Indonesia (QRIS GoPay, OVO, ShopeePay, VA BCA/Mandiri/BRI) | Pendaftaran Akun Bisnis / Sandbox |
| **Google Cloud Console** | Google Blogger API v3 OAuth Client | Gratis (Quotas besar) |
| **Cloudinary** | Public WebP Image CDN (bebas gambar broken di Blogger) | Gratis (Free 25GB/bulan) |
| **Cloud Hosting** | Railway / Render / Fly.io / VPS Ubuntu (Dokku / Docker) | Mulai $5/bulan atau Free Tier |

---

## 🗄️ Langkah 1: Setup Database Supabase (PostgreSQL)

1. Buka [Supabase Dashboard](https://supabase.com/) dan buat project baru (misal: `blogger-autopilot-prod`).
2. Masuk ke menu **Project Settings** → **Database** → **Connection string**:
   - Pilih mode **URI** (Connection Pooling port `6543` atau Direct port `5432`).
   - Simpan URI tersebut:
     ```env
     DATABASE_URL=postgresql://postgres.[YOUR-PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
     ```
3. Masuk ke menu **SQL Editor** di dashboard Supabase:
   - Buka file [`schema_supabase.sql`](schema_supabase.sql) pada project ini.
   - Salin seluruh isi skrip dan tempel ke SQL Editor Supabase.
   - Klik **Run**. Seluruh tabel (`users`, `subscriptions`, `blogs`, `articles`, `keywords`) dan **Row-Level Security (RLS)** akan aktif secara otomatis.

---

## 💳 Langkah 2: Setup Midtrans Payment Gateway Indonesia

1. Masuk ke [Midtrans Dashboard](https://dashboard.midtrans.com/):
   - Gunakan environment **Sandbox** untuk uji coba, atau **Production** saat live.
2. Buka menu **Settings** → **Access Keys**:
   - Salin **Client Key** dan **Server Key**.
3. Buka menu **Settings** → **Configuration**:
   - Masukkan **Payment Notification URL**:
     ```
     https://[DOMAIN-SAAS-ANDA].com/api/billing/midtrans/webhook
     ```
4. Masuk ke menu **Snap Preferences** → **Payment Channels**:
   - Pastikan channel aktif: **QRIS (GoPay, OVO, Dana, LinkAja, ShopeePay)** dan **Bank Transfer (BCA, Mandiri, BRI, BNI, Permata)**.

---

## 🌐 Langkah 3: Setup Google Cloud OAuth (Blogger API v3)

1. Masuk ke [Google Cloud Console](https://console.cloud.google.com/):
   - Pilih project Anda dan aktifkan **Blogger API v3**.
2. Masuk ke **APIs & Services** → **OAuth consent screen**:
   - Pilih User Type: **External**.
   - Tambahkan Scope: `https://www.googleapis.com/auth/blogger`.
3. Masuk ke **Credentials** → Buat **OAuth client ID** (Application type: **Web application**):
   - **Authorized JavaScript origins**:
     ```
     https://[DOMAIN-SAAS-ANDA].com
     ```
   - **Authorized redirect URIs**:
     ```
     https://[DOMAIN-SAAS-ANDA].com/api/auth/google/callback
     ```
4. Unduh file kredensial JSON dan simpan di root server sebagai `client_secret.json`.

---

## ⚙️ Langkah 4: Konfigurasi Environment Variables (`.env`)

Buat file `.env` di server produksi dengan konfigurasi berikut:

```env
# Server Host & Port
PORT=8090
HOST=0.0.0.0
APP_BASE_URL=https://[DOMAIN-SAAS-ANDA].com

# Supabase Managed Database
DATABASE_URL=postgresql://postgres.[YOUR-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Keamanan Token & Sesi (Wajib diganti dengan string acak panjang!)
JWT_SECRET_KEY=kunci-rahasia-jwt-32-karakter-min-harus-sangat-rahasia-dan-kuat
ENCRYPTION_SECRET_KEY=kunci-aes-256-enkripsi-oauth-token-blogger-di-database

# Indonesian Payment Gateway (Midtrans)
MIDTRANS_SERVER_KEY=SB-Mid-server-xxxxxxxxxxxxxxxxx
MIDTRANS_CLIENT_KEY=SB-Mid-client-xxxxxxxxxxxxxxxxx
MIDTRANS_IS_PRODUCTION=false # Ubah ke true saat go-live

# AI Engines
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxx
# OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxx

# Public Image CDN (Cloudinary)
CLOUDINARY_URL=cloudinary://[API_KEY]:[API_SECRET]@[CLOUD_NAME]
```

---

## 🐳 Langkah 5: Deployment dengan Docker & Docker Compose

Proyek ini telah dilengkapi dengan [`Dockerfile`](Dockerfile) dan [`docker-compose.yml`](docker-compose.yml) siap pakai.

### Opsi A: Menggunakan Docker Compose (VPS / Server Pribadi)
```bash
# 1. Clone repository ke server VPS
git clone https://github.com/[username]/blogger-autopilot.git /opt/blogger-autopilot
cd /opt/blogger-autopilot

# 2. Siapkan file .env dan client_secret.json
cp .env.example .env
nano .env

# 3. Jalankan container di background
docker compose up -d --build

# 4. Cek log container
docker compose logs -f web
```

### Opsi B: 1-Click Deployment di Railway / Render
1. Hubungkan repository GitHub Anda ke **Railway.app** atau **Render.com**.
2. Pilih deployment berbasis **Dockerfile**.
3. Tambahkan seluruh isi variabel dari `.env` ke menu **Environment Variables** di dashboard Railway/Render.
4. Hubungkan custom domain Anda (misal: `autopilot.bisnisanda.com`) dengan SSL otomatis dari Cloudflare / Let's Encrypt.

---

## ⏰ Langkah 6: Menjalankan Autopilot Background Scheduler

Untuk memproses pembuatan draf artikel secara mandiri dan berkala bagi pelanggan aktif yang masih memiliki sisa kuota kredit:

### Menjalankan Scheduler Daemon via Systemd (Ubuntu VPS):
Buat file service di `/etc/systemd/system/autopilot-scheduler.service`:
```ini
[Unit]
Description=Blogger Auto-Pilot SaaS Background Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/blogger-autopilot
ExecStart=/opt/blogger-autopilot/.venv/bin/python autopilot_scheduler.py 3600
Restart=always
RestartSec=10
EnvironmentFile=/opt/blogger-autopilot/.env

[Install]
WantedBy=multi-user.target
```
Aktifkan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now autopilot-scheduler
sudo systemctl status autopilot-scheduler
```

---

## 🩺 Langkah 7: Verifikasi Diagnostik Kesiapan Rilis

Sebelum mengumumkan platform kepada publik, jalankan utilitas audit mandiri:
```bash
python check_saas_readiness.py
```
Pastikan seluruh indikator menampilkan status **`✅ [PASS]`**.

---

## 🛠️ Langkah 8: Utilitas Manajemen SaaS via CLI (`manage_saas.py`)

Di server produksi atau VPS, operator dapat menggunakan utilitas CLI untuk mengelola penyewa tanpa perlu membuka database:

1. **Melihat Ringkasan Metrik Bisnis & Estimasi MRR:**
   ```bash
   python manage_saas.py stats
   ```
2. **Melihat Daftar Seluruh Penyewa & Kuota Kredit:**
   ```bash
   python manage_saas.py list
   ```
3. **Membuat Akun Administrator Baru:**
   ```bash
   python manage_saas.py create-user --email=admin@domain.com --password="PasswordKuat123!" --role=admin --plan=pro
   ```
4. **Mengubah Paket Langganan Tenant Secara Manual:**
   ```bash
   python manage_saas.py set-plan --email=creator@gmail.com --plan=pro
   ```
5. **Memberikan Bonus Kredit Tambahan (Kompenasasi/Loyalitas):**
   ```bash
   python manage_saas.py add-credits --email=creator@gmail.com --amount=50
   ```
6. **Memicu Siklus Autopilot Global Secara Instan:**
   ```bash
   python manage_saas.py run-cycle
   ```

Platform Anda kini siap menerima pendaftaran pelanggan, memproses pembayaran via QRIS/VA, dan mengelola ratusan blog Blogger secara autopilot! 🚀
