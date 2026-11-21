# Panduan Deployment & Rollback Produksi — Blogger Auto-Pilot SaaS

Dokumen ini adalah *runbook* operasional untuk merilis **Blogger Auto-Pilot SaaS** ke server produksi (VPS Linux / Docker / Managed PostgreSQL) serta prosedur *rollback* darurat.

---

## 1. Prasyarat Wajib Sebelum Go-Live

Salin `.env.production.example` menjadi `.env` di server produksi dan pastikan seluruh nilai di bawah **sudah diisi dengan kredensial asli** (aplikasi akan otomatis *fail-fast* menolak start jika secret JWT/AES masih kosong atau memakai placeholder saat `ENVIRONMENT=production`):

| Variabel | Syarat Produksi |
| :--- | :--- |
| `ENVIRONMENT` | `production` |
| `SECURE_COOKIES` | `true` |
| `APP_BASE_URL` | `https://app.namadomainanda.com` (wajib HTTPS) |
| `DATABASE_URL` | URI PostgreSQL / Supabase (`postgresql://...`) |
| `JWT_SECRET_KEY` | Minimal 32 karakter acak (`openssl rand -hex 32`) |
| `ENCRYPTION_SECRET_KEY` | Minimal 32 karakter acak (`openssl rand -hex 32`) |
| `CRON_SECRET_KEY` | Token acak untuk endpoint `/api/cron/trigger-cycle` |
| `MIDTRANS_IS_PRODUCTION` | `true` beserta `MIDTRANS_SERVER_KEY` & `MIDTRANS_CLIENT_KEY` live |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | Minimal 1 kunci LLM aktif (disarankan keduanya untuk fallback) |
| `CLOUDINARY_URL` | Kunci Cloudinary untuk CDN gambar publik HTTPS permanen |
| `GOOGLE_CLIENT_SECRETS_FILE` | Path ke `client_secret.json` dengan Authorized Redirect URI `https://app.namadomainanda.com/api/auth/google/callback` |

---

## 2. Langkah Deployment Produksi

### A. Backup Database Sebelum Migrasi
```bash
# Backup snapshot PostgreSQL sebelum upgrade schema
pg_dump "$DATABASE_URL" > "backup_pre_deploy_$(date +%Y%m%d_%H%M%S).sql"
```

### B. Migrasi Schema & Verifikasi Kesiapan
```bash
# 1. Jalankan migrasi database resmi
.venv/bin/alembic upgrade head

# 2. Jalankan diagnostik kesiapan environment
.venv/bin/python3 scripts/check_saas_readiness.py

# 3. Buat akun Superadmin pertama (interaktif, tanpa hardcode password)
.venv/bin/python3 scripts/create_admin.py
```

### C. Jalankan Layanan (Docker Compose atau Systemd)

**Opsi Docker Compose:**
```bash
docker compose up -d --build
curl -fsS http://127.0.0.1:8090/health
```

**Opsi Systemd Worker (VPS Bare-Metal):**
```bash
sudo cp scripts/blogger-autopilot-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blogger-autopilot-worker
sudo systemctl status blogger-autopilot-worker
```

### D. Reverse Proxy Nginx & SSL Let's Encrypt
```bash
sudo cp scripts/nginx-blogger-autopilot.conf.example /etc/nginx/sites-available/blogger-autopilot
sudo ln -s /etc/nginx/sites-available/blogger-autopilot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d app.namadomainanda.com
```

### E. Konfigurasi Webhook & OAuth Eksternal
1. **Midtrans Production Dashboard:** Set *Payment Notification URL* ke `https://app.namadomainanda.com/api/billing/midtrans/webhook`.
2. **Google Cloud Console (OAuth Consent Screen):** Ubah status dari *Testing* ke **In Production** dan daftarkan `https://app.namadomainanda.com/api/auth/google/callback` pada Authorized Redirect URIs.

---

## 3. Verifikasi Smoke Test Pasca-Rilis (5 Menit Pertama)

1. `curl -I https://app.namadomainanda.com/health` → HTTP `200`, database `postgresql`, header `Strict-Transport-Security` dan `X-Frame-Options: DENY` aktif.
2. Buka `https://app.namadomainanda.com` sebagai tamu → menampilkan Landing Page publik.
3. Login sebagai Superadmin → buka `👑 Admin Console` → pastikan KPI, tab Workspaces, dan Global Audit Trail termuat tanpa error.
4. Uji transaksi nominal kecil atau verifikasi Snap popup terbuka pada mode Production.

---

## 4. Prosedur Rollback Darurat

Jika terjadi regresi kritis pasca-deploy:

```bash
# 1. Hentikan traffic/container atau checkout commit stabil sebelumnya
git log --oneline -5
git checkout <COMMIT_HASH_STABIL>

# 2. Jika migrasi schema perlu dikembalikan 1 versi ke belakang:
.venv/bin/alembic downgrade -1

# 3. Atau pulihkan snapshot PostgreSQL jika terjadi kerusakan data:
# psql "$DATABASE_URL" < backup_pre_deploy_YYYYMMDD_HHMMSS.sql

# 4. Restart aplikasi & verifikasi health endpoint
docker compose up -d --build
curl -fsS http://127.0.0.1:8090/health
```

