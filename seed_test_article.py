import sqlite3
import sys
from db import DB_PATH

def seed_article():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Cek apakah artikel sudah ada
    existing = c.execute("SELECT id FROM articles WHERE target_keyword = 'cara optimasi core web vitals blogger'").fetchone()
    if existing:
        print('Article already seeded with ID:', existing[0])
        conn.close()
        return
        
    title = 'Cara Optimasi Core Web Vitals Blogger (Skor 90+ Mobile)'
    keyword = 'cara optimasi core web vitals blogger'
    meta = 'Panduan lengkap cara optimasi Core Web Vitals Blogger hingga skor 90+. Pelajari langkah praktis atasi LCP, INP, dan CLS untuk ranking 1 Google!'
    labels = 'Blogger, SEO, Web Performance, Tutorial'
    
    content_html = '''<p><strong>Cara optimasi Core Web Vitals Blogger</strong> berfokus pada tiga metrik utama: Largest Contentful Paint (LCP) di bawah 2.5 detik, Interaction to Next Paint (INP) di bawah 200 ms, dan Cumulative Layout Shift (CLS) di bawah 0.1 dengan menyingkirkan script penghambat render serta mengompresi aset gambar.</p>

<p>Google menjadikan Core Web Vitals sebagai sinyal peringkat resmi dalam algoritma pencarian. Bagi pengguna platform Blogger (Blogspot), keterbatasan akses server sering kali dianggap kendala, padahal optimasi pada level template dan rendering HTML sudah lebih dari cukup untuk meraih skor performa hijau di Google PageSpeed Insights.</p>

<h2>Tolak Ukur 3 Metrik Inti Core Web Vitals</h2>
<p>Sebelum melakukan perbaikan kode tema, pahami standar ambang batas yang ditentukan oleh Google:</p>

<table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%; margin: 15px 0; border-color: #334155;">
  <thead>
    <tr style="background-color: #1e293b; color: #f8fafc;">
      <th>Metrik</th>
      <th>Fokus Evaluasi</th>
      <th>Target Skor Baik</th>
      <th>Penyebab Utama di Blogger</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>LCP</strong></td>
      <td>Kecepatan muat konten terbesar</td>
      <td>&lt; 2.5 detik</td>
      <td>Gambar banner tidak terkompresi / font pihak ketiga</td>
    </tr>
    <tr>
      <td><strong>INP</strong></td>
      <td>Responsivitas interaksi halaman</td>
      <td>&lt; 200 ms</td>
      <td>Eksekusi JavaScript berat dari widget eksternal</td>
    </tr>
    <tr>
      <td><strong>CLS</strong></td>
      <td>Stabilitas visual tata letak</td>
      <td>&lt; 0.1</td>
      <td>Gambar dan iklan tanpa atribut width & height</td>
    </tr>
  </tbody>
</table>

<h2>4 Langkah Praktis Optimasi Core Web Vitals di Blogger</h2>

<h3>1. Terapkan Format WebP dan Responsive Sizing</h3>
<p>Ganti seluruh gambar artikel ke format WebP. Server Google User Content di Blogger mendukung parameter otomatis, namun pastikan tag gambar selalu menyertakan atribut eksplisit <code>width</code> dan <code>height</code> untuk mencegah pergeseran layout mendadak (CLS):</p>

<pre><code>&lt;img src="https://placehold.co/800x450" width="800" height="450" alt="Optimasi LCP Blogger" loading="lazy" /&gt;</code></pre>

<h3>2. Defer JavaScript Eksternal</h3>
<p>Widget statistik, komentar pihak ketiga, atau script analitik yang dipasang langsung di header sering memblokir jalur rendering utama (Critical Rendering Path). Tambahkan atribut <code>defer</code> pada script yang tidak kritikal:</p>

<pre><code>&lt;script src="https://example.com/widget.js" defer&gt;&lt;/script&gt;</code></pre>

<h3>3. Optimasi Google Fonts dengan preconnect</h3>
<p>Blogger secara default memanggil font melalui CSS eksternal. Percepat jabat tangan DNS dengan menambahkan rel preconnect di dalam tag <code>&lt;head&gt;</code> template Blogger Anda:</p>

<pre><code>&lt;link rel="preconnect" href="https://fonts.googleapis.com" crossorigin /&gt;
&lt;link rel="preconnect" href="https://fonts.gstatic.com" crossorigin /&gt;</code></pre>

<h3>4. Bersihkan Bundle CSS Bawaan yang Tidak Digunakan</h3>
<p>Banyak template Blogger lama menyertakan ratusan baris CSS bawaan (seperti CSS bundle bawaan layout v1/v2). Matikan bundle default yang berlebihan dan gunakan CSS ringkas terintegrasi.</p>

<h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>

<h3>Apakah blog gratisan Blogspot bisa dapat skor 90+ di PageSpeed?</h3>
<p>Bisa. Platform Blogger dihosting langsung di infrastruktur CDN Google yang sangat cepat. Skor lambat biasanya diakibatkan oleh tema yang terlalu banyak memasang efek JavaScript dan gambar tanpa optimasi.</p>

<h3>Mengapa skor CLS tiba-tiba merah setelah pasang AdSense?</h3>
<p>Unit iklan responsif sering mendorong konten ke bawah saat iklan baru dimuat. Solusinya adalah membungkus slot iklan dengan container <code>&lt;div&gt;</code> yang memiliki batas tinggi minimum (min-height tetap).</p>

<h3>Berapa lama waktu yang dibutuhkan Google untuk memperbarui skor Core Web Vitals?</h3>
<p>Data Chrome User Experience Report (CrUX) dievaluasi dalam siklus bergulir 28 hari dari kunjungan pengguna nyata (Field Data).</p>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Apakah blog gratisan Blogspot bisa dapat skor 90+ di PageSpeed?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Bisa. Platform Blogger dihosting di infrastruktur CDN Google yang sangat cepat, penurunan skor biasanya berasal dari template berat dan script eksternal."
      }
    },
    {
      "@type": "Question",
      "name": "Mengapa skor CLS tiba-tiba merah setelah pasang AdSense?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Unit iklan responsif mendorong konten saat dimuat. Berikan pembungkus div dengan CSS min-height tetap untuk menstabilkan posisi."
      }
    }
  ]
}
</script>'''

    c.execute('''
        INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, status)
        VALUES (?, ?, ?, ?, ?, 'draft')
    ''', (title, keyword, meta, content_html, labels))
    
    c.execute('''
        INSERT OR IGNORE INTO keywords (keyword, search_intent, status)
        VALUES (?, ?, 'in_progress')
    ''', (keyword, 'Informational'))
    
    conn.commit()
    conn.close()
    print('SUCCESS: Sample article inserted into DB!')

if __name__ == '__main__':
    seed_article()
