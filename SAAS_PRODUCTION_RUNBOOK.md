# Panduan Rilis Produksi SaaS (Production Runbook)
## Blogger Auto-Pilot SaaS — Menuju Peluncuran Publik

Dokumen ini adalah panduan langkah-demi-langkah resmi (*production runbook*) untuk meluncurkan platform **Blogger Auto-Pilot SaaS** ke lingkungan *cloud production* dengan arsitektur yang telah diaudit dan disepakati.

---

## 1. Arsitektur Target Produksi

```
[ Pengguna Publik / Internet ]
              │ (HTTPS:443)
              ▼
    [ Nginx Reverse Proxy + SSL Let's Encrypt ]
              │ (HTTP:8090)
              ▼
┌───────────────────────────────────────────────────────────┐
│ Cloud VPS / Server Docker                                 │
│                                                           │
│  ┌───────────────────────┐     ┌───────────────────────┐  │
│  │ Container: web        │     │ Container: scheduler  │  │
│  │ (FastAPI App & UI)    │     │ (Autopilot Daemon)    │  │
│  └──────────┬────────────┘     └──────────┬────────────┘  │
└─────────────┼─────────────────────────────┼───────────────┘
              │                             │
              ▼                             ▼
┌───────────────────────────┐ ┌─────────────────────────────┐
│ Supabase Managed Postgres │ │ Layanan Eksternal           │
│ - Users & Subscriptions   │ │ - Google Blogger OAuth 2.0  │
│ - Blogs, Articles, Keys   │ │ - Google Gemini / Groq AI   │
│ - Enkripsi AES-256 Tokens │ │ - Midtrans IDR Payment Snap │
│                           │ │ - Cloudinary WebP CDN       │
└───────────────────────────┘ └─────────────────────────────┘
```

---

## 2. Langkah 1: Persiapan Database PostgreSQL (Supabase)

1. Buka [Supabase Dashboard](https://supabase.com) dan buat proyek baru (*New Project*).
2. Simpan kata sandi database Anda (*Database Password*).
3. Buka menu **SQL Editor** di Supabase.
4. Salin isi berkas `schema_supabase.sql` dari repositori ini, lalu tempelkan dan jalankan (*Run*) di SQL Editor Supabase.
5. Ambil URI koneksi database dari menu **Settings > Database > Connection string > URI (Transaction / Session)**:
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
6. Masukkan URI tersebut ke dalam berkas `.env` server pada variabel `DATABASE_URL`.

---

## 3. Langkah 2: Registrasi Google Cloud Console (OAuth 2.0)

Agar pengguna SaaS dapat menghubungkan akun Google dan blog mereka dengan 1 klik:

1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat proyek baru: `Blogger Auto-Pilot Platform`.
3. Buka **APIs & Services > Library**, cari dan aktifkan:
   - **Blogger API v3**
4. Buka **APIs & Services > OAuth consent screen**:
   - Tipe Pengguna: **External**.
   - Nama Aplikasi: `Blogger Auto-Pilot`.
   - Email Dukungan & Pengembang: Email Anda.
   - Scopes: Tambahkan `https://www.googleapis.com/auth/blogger`.
   - Di tahap awal pengujian, tambahkan email tester di menu **Test Users**, atau ajukan **Publish App** ke Google agar dapat diakses tanpa batasan tester.
5. Buka **APIs & Services > Credentials > Create Credentials > OAuth client ID**:
   - Tipe Aplikasi: **Web application**.
   - Nama: `Blogger SaaS Production Client`.
   - **Authorized JavaScript origins**:
     - `https://app.namadomainanda.com`
   - **Authorized redirect URIs**:
     - `https://app.namadomainanda.com/api/auth/google/callback`
6. Unduh berkas JSON kredensial tersebut, ubah namanya menjadi `client_secret.json`, dan letakkan di root direktori aplikasi di server.

---

## 4. Langkah 3: Aktivasi Midtrans Production Gateway

1. Buka [Midtrans Dashboard](https://dashboard.midtrans.com) dan beralih ke mode **Production** di pojok kanan atas.
2. Buka menu **Settings > Access Keys**:
   - Salin **Merchant Server Key** ke variabel `MIDTRANS_SERVER_KEY`.
   - Salin **Merchant Client Key** ke variabel `MIDTRANS_CLIENT_KEY`.
   - Atur `MIDTRANS_IS_PRODUCTION=true`.
3. Buka menu **Settings > Configuration**:
   - **Payment Notification URL**: Isi dengan `https://app.namadomainanda.com/api/billing/midtrans/webhook`.
   - **Finish Redirect URL**: Isi dengan `https://app.namadomainanda.com/?payment_status=finish`.
   - **Error Redirect URL**: Isi dengan `https://app.namadomainanda.com/?payment_status=error`.

---

## 5. Langkah 4: Kunci API AI & CDN Gambar

1. **Google Gemini (Primary AI)**:
   - Dapatkan API key dari [Google AI Studio](https://aistudio.google.com/).
   - Masukkan ke `GEMINI_API_KEY`.
2. **Groq Cloud (Fallback AI)**:
   - Dapatkan API key dari [Groq Console](https://console.groq.com/).
   - Masukkan ke `GROQ_API_KEY`.
3. **Cloudinary (CDN Gambar Publik)**:
   - Buat akun gratis di [Cloudinary](https://cloudinary.com/).
   - Salin **API Environment variable** (format: `cloudinary://<api_key>:<api_secret>@<cloud_name>`).
   - Masukkan ke `CLOUDINARY_URL`.

---

## 6. Langkah 5: Deployment ke Server Cloud VPS (Docker)

### A. Salin File Konfigurasi ke Server
```bash
# Clone repository
git clone https://github.com/bagues33/blogger-autopilot.git /opt/blogger-autopilot
cd /opt/blogger-autopilot

# Buat file .env dari template produksi
cp .env.production.example .env

# Edit .env dengan kredensial riil Anda
nano .env

# Pastikan client_secret.json dari Google sudah diletakkan
# /opt/blogger-autopilot/client_secret.json
```

### B. Jalankan Container Docker
```bash
docker compose up -d --build
```
Kedua layanan akan berjalan di background:
- `blogger-autopilot-web`: Menangani web dashboard dan API pada port 8090.
- `blogger-autopilot-scheduler`: Menjalankan siklus autopilot per jam secara otomatis.

---

## 7. Langkah 6: Konfigurasi Nginx & SSL Gratis (Certbot)

Pasang Nginx di VPS induk untuk menangani domain dan HTTPS:

```nginx
# /etc/nginx/sites-available/blogger-saas
server {
    server_name app.namadomainanda.com;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktifkan konfigurasi dan terbitkan sertifikat SSL Let's Encrypt:
```bash
sudo ln -s /etc/nginx/sites-available/blogger-saas /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d app.namadomainanda.com
```

---

## 8. Verifikasi Pasca-Deployment (Smoke Test Checklist)

Sebelum membuka platform untuk pengguna umum, lakukan pengecekan berikut:

- [ ] Buka `https://app.namadomainanda.com/health` di browser. Respons harus bernilai `"status": "healthy"`.
- [ ] Daftarkan akun baru melalui tombol **Daftar Akun**. Pastikan kuota Free (3 kredit) aktif.
- [ ] Klik **Hubungkan Akun Google** dan verifikasi redirect Google OAuth sukses serta blog otomatis terdaftar.
- [ ] Masuk ke akun Superadmin (`admin@bagustech.id`). Buka Cockpit Superadmin dan verifikasi metrik tenant.
- [ ] Uji reset kata sandi tenant melalui tombol **Reset Pwd** di tabel tenant Superadmin.
- [ ] Uji upgrade paket ke Midtrans Snap. Pastikan popup Midtrans muncul dengan nominal yang benar.
- [ ] Uji klik **Buat Draf AI** dan pastikan artikel berhasil digenerasi oleh Gemini Flash dan tersimpan rapi dengan skema FAQ Schema.

Sistem SaaS Anda kini siap menerima pengguna dan menghasilkan pendapatan berulang (MRR)!
