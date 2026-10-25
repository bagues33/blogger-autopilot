import json
import sqlite3
from datetime import datetime
from db import DB_PATH

target_keyword = 'cara integrasi api gemini di web modern'
title = 'Cara Integrasi API Gemini di Web Modern: Panduan Praktis'
meta_desc = 'Pelajari cara integrasi API Gemini di web modern langkah demi langkah. Dapatkan tips keamanan API key, kode praktis, dan optimasi performanya di sini!'

# Direct Answer Hook (40-50 words)
# Rich elements: comparison table, structured listicle, code blocks
# Internal link: https://bagustechnologia.blogspot.com/2026/10/cara-optimasi-core-web-vitals-blogger.html
# No AI cliches ('Di era digital', 'Seperti yang kita tahu')
# No heading 'Kesimpulan'
# Schema FAQ JSON-LD included

html_content = '''<p><strong>Cara integrasi API Gemini di web modern</strong> dilakukan dengan membuat API key di Google AI Studio, menyiapkan server-side proxy atau backend endpoint untuk menjaga kerahasiaan kredensial, lalu mengirimkan request JSON terstruktur ke endpoint Gemini model terbaru menggunakan SDK resmi atau HTTP fetch.</p>

<p>Menambahkan kapabilitas AI ke dalam aplikasi web bukan lagi sekadar tren gimmick, melainkan kebutuhan fungsional untuk fitur seperti smart search, ringkasan konten otomatis, chatbot interaktif, hingga analisis data real-time. Namun, banyak developer pemula melakukan kesalahan fatal: mengekspos API key langsung di sisi frontend (client-side JavaScript). Melalui panduan praktis ini, Anda akan mempelajari arsitektur integrasi yang aman, efisien, dan siap produksi.</p>

<h2>Arsitektur Integrasi API Gemini: Client-Side vs Server-Side Proxy</h2>

<p>Sebelum menulis sebaris kode pun, pemahaman mendasar mengenai alur komunikasi data antara user interface, server aplikasi, dan Google Generative AI API sangatlah penting. Menggunakan API key langsung di browser membuka celah kebocoran kuota dan penyalahgunaan billing oleh pihak yang tidak bertanggung jawab.</p>

<table border="1" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
  <thead>
    <tr style="background-color: #f2f2f2;">
      <th>Parameter Evaluasi</th>
      <th>Direct Client-Side (Frontend Saja)</th>
      <th>Server-Side Proxy (Direkomendasikan)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Keamanan API Key</strong></td>
      <td>Sangat Rentan (Terlihat di inspect network browser)</td>
      <td>Aman (Tersimpan rahasia di environment variable)</td>
    </tr>
    <tr>
      <td><strong>Rate Limiting & Caching</strong></td>
      <td>Sulit dikontrol secara terpusat</td>
      <td>Dapat dikontrol dengan Redis / In-memory cache</td>
    </tr>
    <tr>
      <td><strong>Kontrol Token & Biaya</strong></td>
      <td>Pengguna bisa memodifikasi payload semaunya</td>
      <td>Payload divalidasi ketat sebelum diteruskan</td>
    </tr>
    <tr>
      <td><strong>Latensi Jaringan</strong></td>
      <td>1 hop (Browser langsung ke Google)</td>
      <td>2 hop (Browser &rarr; Backend App &rarr; Google)</td>
    </tr>
    <tr>
      <td><strong>Kesesuaian Produksi</strong></td>
      <td>Hanya untuk prototipe lokal / hackathon kilat</td>
      <td>Wajib untuk aplikasi production-ready</td>
    </tr>
  </tbody>
</table>

<h2>Persiapan Kebutuhan Integrasi</h2>

<p>Pastikan Anda telah menyiapkan prasyarat dasar berikut sebelum memulai implementasi:</p>
<ul>
  <li><strong>Google AI Studio Account:</strong> Kunjungi portal resmi Google AI Studio untuk mendaftar dan menghasilkan API key.</li>
  <li><strong>Runtime Environment:</strong> Node.js versi 18+ (LTS) atau Python 3.10+ di sisi backend.</li>
  <li><strong>Manajemen Environment:</strong> Gunakan file <code>.env</code> untuk menyimpan konfigurasi sensitif.</li>
  <li><strong>Frontend Modern:</strong> Framework modern seperti React, Vue, Svelte, atau sekadar Vanilla HTML/JS dengan modern Fetch API.</li>
</ul>

<h2>Langkah 1: Mendapatkan API Key dan Setup Environment</h2>

<p>Langkah pertama adalah membuat kredensial akses di Google AI Studio. Ikuti alur berikut:</p>
<ol>
  <li>Buka dashboard <strong>Google AI Studio</strong> dan login menggunakan akun Google Anda.</li>
  <li>Klik tombol <strong>Get API key</strong> di navigasi samping.</li>
  <li>Pilih <strong>Create API key in new project</strong> atau kaitkan dengan Google Cloud Project yang telah ada.</li>
  <li>Salin token string yang dihasilkan, lalu simpan di file <code>.env</code> proyek backend Anda:</li>
</ol>

<pre><code># File: .env
GEMINI_API_KEY=AIzaSyYourGeneratedSecretKeyHere
PORT=3000
</code></pre>

<p>Tambahkan file <code>.env</code> ke dalam <code>.gitignore</code> agar kredensial ini tidak sengaja terdorong ke repositori publik seperti GitHub.</p>

<h2>Langkah 2: Membangun Server-Side Proxy dengan Node.js Express</h2>

<p>Di sisi backend, kita akan menginstal library resmi Google Gen AI SDK (<code>@google/genai</code> atau <code>@google/generative-ai</code>) dan Express untuk membuat REST endpoint sederhana.</p>

<pre><code>npm install express dotenv cors @google/genai
</code></pre>

<p>Berikut adalah implementasi endpoint backend <code>/api/generate</code> yang menerima prompt teks dari frontend dan mengembalikan respon teks dari model Gemini:</p>

<pre><code>// File: server.js
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

app.post('/api/generate', async (req, res) => {
  try {
    const { prompt } = req.body;
    if (!prompt || typeof prompt !== 'string') {
      return res.status(400).json({ error: 'Prompt wajib diisi dan berupa string valid.' });
    }

    // Memanggil model Gemini 2.5 Flash untuk kecepatan dan efisiensi biaya
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
    });

    return res.json({
      success: true,
      result: response.text
    });
  } catch (error) {
    console.error('Error saat menghubungi Gemini API:', error);
    return res.status(500).json({
      success: false,
      error: 'Terjadi kegagalan komunikasi dengan model AI.'
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server API proxy aktif di http://localhost:${PORT}`);
});
</code></pre>

<h2>Langkah 3: Menghubungkan Frontend Web Modern</h2>

<p>Setelah server proxy siap, kita dapat membuat antarmuka web modern yang mengirimkan request menggunakan <code>fetch()</code> secara asinkron. Antarmuka ini dirancang responsif, interaktif, dan dilengkapi penanganan status loading serta rendering markdown dasar.</p>

<pre><code>&lt;!-- File: index.html --&gt;
&lt;!DOCTYPE html&gt;
&lt;html lang="id"&gt;
&lt;head&gt;
  &lt;meta charset="UTF-8"&gt;
  &lt;meta name="viewport" content="width=device-width, initial-scale=1.0"&gt;
  &lt;title&gt;Demo Integrasi Gemini API&lt;/title&gt;
  &lt;style&gt;
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; line-height: 1.6; }
    textarea { width: 100%; height: 120px; padding: 12px; border-radius: 8px; border: 1px solid #ccc; font-size: 16px; }
    button { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; margin-top: 10px; }
    button:disabled { background: #94a3b8; cursor: not-allowed; }
    .output-box { margin-top: 24px; padding: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; min-height: 80px; white-space: pre-wrap; }
  &lt;/style&gt;
&lt;/head&gt;
&lt;body&gt;
  &lt;h1&gt;Asisten AI Web Modern&lt;/h1&gt;
  &lt;textarea id="promptInput" placeholder="Tulis pertanyaan atau prompt Anda di sini..."&gt;&lt;/textarea&gt;
  &lt;br&gt;
  &lt;button id="submitBtn" onclick="handleGenerate()"&gt;Kirim Prompt&lt;/button&gt;

  &lt;div class="output-box" id="resultContainer"&gt;Jawaban AI akan muncul di sini...&lt;/div&gt;

  &lt;script&gt;
    async function handleGenerate() {
      const input = document.getElementById('promptInput');
      const btn = document.getElementById('submitBtn');
      const output = document.getElementById('resultContainer');
      
      const promptText = input.value.trim();
      if (!promptText) return;

      btn.disabled = true;
      btn.innerText = 'Memproses jawaban...';
      output.innerText = 'Menghubungi Gemini API via backend proxy...';

      try {
        const response = await fetch('http://localhost:3000/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: promptText })
        });

        const data = await response.json();
        if (data.success) {
          output.innerText = data.result;
        } else {
          output.innerText = 'Gagal: ' + (data.error || 'Terjadi kesalahan sistem.');
        }
      } catch (err) {
        output.innerText = 'Koneksi error: Periksa apakah backend aktif.';
      } finally {
        btn.disabled = false;
        btn.innerText = 'Kirim Prompt';
      }
    }
  &lt;/script&gt;
&lt;/body&gt;
&lt;/html&gt;
</code></pre>

<h2>Optimasi Performa Web dan Pengalaman Pengguna (UX)</h2>

<p>Mengintegrasikan model AI generatif menghadirkan tantangan performa tersendiri, terutama terkait waktu tunggu (Time to First Token / TTFT). Respon LLM seringkali membutuhkan waktu 1 hingga 4 detik sebelum output lengkap selesai dihasilkan. Bila Anda tidak mengoptimasi arsitektur web, skor metrik performa web pengguna akan anjlok.</p>

<p>Untuk memastikan website tetap gesit dan tidak mengalami pergeseran tata letak kumulatif yang mengganggu pengguna mobile, Anda bisa mempelajari prinsip performa pada artikel kami tentang <a href="https://bagustechnologia.blogspot.com/2026/10/cara-optimasi-core-web-vitals-blogger.html">Cara Optimasi Core Web Vitals Blogger (Skor 90+ Mobile)</a>. Beberapa teknik optimasi spesifik untuk integrasi AI antara lain:</p>

<ul>
  <li><strong>Implementasi Streaming Respon (Server-Sent Events / SSE):</strong> Alih-alih menunggu seluruh teks selesai di-generate, gunakan mode streaming (<code>generateContentStream</code>) agar kata per kata langsung mengalir ke layar pengguna secara real-time.</li>
  <li><strong>Skeleton Loading & Placeholder UI:</strong> Sediakan indikator visual berupa skeleton shimmer di kontainer output agar layout tidak melompat secara tiba-tiba (mencegah CLS tinggi).</li>
  <li><strong>In-Memory Caching untuk Prompt Berulang:</strong> Pertanyaan umum yang sering diajukan user dapat disimpan di layer caching seperti Redis atau Cloudflare KV dengan waktu kedaluwarsa (TTL) tertentu untuk memangkas biaya token dan latensi hingga di bawah 50 milidetik.</li>
  <li><strong>Debouncing dan Rate Limiting:</strong> Terapkan batasan request per alamat IP untuk mencegah bot melakukan crawling masif yang menghabiskan kuota API key Anda.</li>
</ul>

<h2>Praktik Terbaik Pengamanan Kredensial di Lingkungan Cloud</h2>

<p>Ketika meluncurkan aplikasi web ke platform hosting publik seperti Vercel, Netlify, Cloudflare Pages, atau VPS Ubuntu, terapkan standar keamanan tingkat enterprise berikut:</p>
<ol>
  <li><strong>Secret Manager & Environment Variables:</strong> Jangan sekali-kali melakukan hardcoding token ke dalam file JavaScript klien. Manfaatkan fitur Environment Variables bawaan penyedia cloud.</li>
  <li><strong>CORS Whitelist:</strong> Batasi konfigurasi Cross-Origin Resource Sharing pada backend Express hanya untuk domain frontend resmi Anda, mencegah domain asing memanfaatkan endpoint API Anda.</li>
  <li><strong>App Check & Recaptcha v3:</strong> Pasang verifikasi bot sebelum pengguna diizinkan mengirim prompt untuk memastikan request berasal dari interaksi manusia sungguhan.</li>
  <li><strong>Quota Limits di Google Cloud Console:</strong> Pasang peringatan kuota harian dan batas maksimal pengeluaran biaya bulanan agar tagihan Anda tetap terkendali.</li>
</ol>

<h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>

<p><strong>Berapa biaya penggunaan Gemini API untuk aplikasi web?</strong><br>Google AI Studio menyediakan paket gratis (Free Tier) dengan kuota rate limit yang sangat cukup untuk tahap pengembangan dan aplikasi skala kecil hingga menengah. Untuk skala produksi tinggi, Anda dapat beralih ke skema Pay-as-you-go melalui penagihan Google Cloud Platform.</p>

<p><strong>Model Gemini mana yang paling optimal untuk integrasi web modern?</strong><br>Gemini 2.5 Flash adalah pilihan paling seimbang untuk aplikasi web interaktif karena menawarkan latensi sangat rendah, kecepatan inferensi tinggi, dan efisiensi biaya token yang jauh lebih ekonomis dibandingkan model Pro.</p>

<p><strong>Apakah aman memanggil Gemini API langsung dari frontend React atau Vue tanpa backend?</strong><br>Sangat tidak disarankan untuk aplikasi publik. Memanggil API langsung dari browser mengharuskan API key disertakan dalam request header, sehingga siapapun dapat melihat dan mencuri key tersebut melalui tab Network di Developer Tools.</p>

<p><strong>Bagaimana cara mengaktifkan streaming output kata demi kata di frontend?</strong><br>Gunakan endpoint berbasis ReadableStream di backend dan tangani respon menggunakan <code>response.body.getReader()</code> di sisi frontend JavaScript dengan decoding TextDecoder.</p>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Berapa biaya penggunaan Gemini API untuk aplikasi web?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Google AI Studio menyediakan paket gratis (Free Tier) dengan kuota rate limit yang memadai untuk pengembangan dan aplikasi skala kecil. Untuk kebutuhan produksi tinggi, tersedia opsi Pay-as-you-go berbasis token."
      }
    },
    {
      "@type": "Question",
      "name": "Model Gemini mana yang paling optimal untuk integrasi web modern?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Gemini 2.5 Flash adalah model paling direkomendasikan untuk web karena menawarkan latensi sangat rendah, performa inferensi tinggi, serta biaya token yang sangat efisien."
      }
    },
    {
      "@type": "Question",
      "name": "Apakah aman memanggil Gemini API langsung dari frontend React atau Vue tanpa backend?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Tidak aman untuk aplikasi publik karena API key akan terlihat di inspect tab Network browser. Selalu gunakan server-side proxy atau backend serverless function."
      }
    },
    {
      "@type": "Question",
      "name": "Bagaimana cara mengaktifkan streaming output kata demi kata di frontend?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Gunakan metode generateContentStream di backend dan konsumsi aliran data di frontend menggunakan ReadableStream dan TextDecoder secara asinkron."
      }
    }
  ]
}
</script>'''

# Calculate word count (rough estimate from text)
import re
text_only = re.sub(r'<[^>]+>', ' ', html_content)
words = [w for w in text_only.split() if w.strip()]
word_count = len(words)
print(f"Calculated word count: {word_count}")

# Connect to database
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. Update keyword status to in_progress
cur.execute("UPDATE keywords SET status = 'in_progress' WHERE id = 4")

# 2. Insert draft article
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
labels = 'Web Development, Artificial Intelligence, Gemini API, JavaScript, Tutorial'

cur.execute('''
    INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
''', (title, target_keyword, meta_desc, html_content, labels, now_str, now_str))

new_article_id = cur.lastrowid
conn.commit()

print(f"Article inserted with ID: {new_article_id}")

# Verify database state
print('=== KEYWORD 4 CURRENT STATE ===')
print(cur.execute('SELECT * FROM keywords WHERE id = 4').fetchone())

print('=== NEW ARTICLE ROW ===')
print(cur.execute('SELECT id, title, target_keyword, status, created_at FROM articles WHERE id = ?', (new_article_id,)).fetchone())

conn.close()
