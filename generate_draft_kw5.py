import re
import json
import sqlite3
from datetime import datetime

target_keyword = 'tips prompt engineering untuk software engineer'
title = 'Tips Prompt Engineering untuk Software Engineer Praktis'
meta_desc = 'Pelajari tips prompt engineering untuk software engineer paling efektif. Temukan framework prompt, contoh nyata debugging, dan optimasi output AI sekarang!'

# Verifikasi panjang
assert 50 <= len(title) <= 60, f'Title length invalid: {len(title)}'
assert 140 <= len(meta_desc) <= 155, f'Meta desc length invalid: {len(meta_desc)}'

html_content = '''<p><strong>Tips prompt engineering untuk software engineer</strong> berfokus pada pemberian konteks arsitektur yang spesifik, pembatasan ruang lingkup instruksi (role and constraints), penyediaan contoh input-output (few-shot prompting), serta penentuan format respon terstruktur guna menghasilkan kode yang akurat, modular, dan siap produksi tanpa halusinasi.</p>

<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=1200&auto=format&fit=crop&q=80" alt="Tips prompt engineering untuk software engineer dalam menulis instruksi coding yang presisi" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  <figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">Ilustrasi interaksi rekayasa prompt kode program pada lingkungan pengembangan software.</figcaption>
</figure>

<p>Banyak developer menggunakan model bahasa besar (LLM) seperti Claude, ChatGPT, atau Gemini sekadar sebagai mesin pencari canggih dengan mengetikkan instruksi ambigu. Pendekatan kasual ini sering menghasilkan kode usang, logika yang rentan bug, atau pola arsitektur yang tidak konsisten dengan basis kode yang sedang dibangun. Menguasai rekayasa prompt bukanlah soal merangkai kata puitis, melainkan menyusun spesifikasi teknis yang tidak memiliki celah interpretasi.</p>

<p>Saat Anda memanfaatkan <a href="https://bagustechnologia.blogspot.com/2026/10/rekomendasi-ai-coding-assistant-gratis.html" target="_blank" rel="noopener">rekomendasi AI coding assistant gratis untuk VS Code</a>, kualitas output baris kode yang dihasilkan sangat bergantung pada instruksi awal yang Anda masukkan. Tanpa arahan kontekstual yang matang, model AI cenderung berspekulasi dan mengambil asumsi liar yang justru memperlambat alur kerja.</p>

<h2>Mengapa Software Engineer Membutuhkan Teknik Prompt Khusus?</h2>

<p>Pemrograman menuntut determinisme logika, kepatuhan tipe data, dan efisiensi memori. Berbeda dengan pembuatan artikel umum di mana variasi frasa disambut baik, kode program harus berjalan tanpa kompromi sintaksis maupun runtime exception.</p>

<p>Ada tiga tantangan teknis utama yang berhasil diselesaikan melalui penerapan <strong>tips prompt engineering untuk software engineer</strong> yang terstandarisasi:</p>

<ul>
  <li><strong>Mengeliminasi Halusinasi Library dan Versi:</strong> LLM kerap mengarang nama fungsi atau menggunakan API versi lama yang sudah deprecated. Prompt yang baik menyertakan batasan versi library secara eksplisit.</li>
  <li><strong>Menjaga Gaya Arsitektur Proyek:</strong> Memastikan potongan kode baru mematuhi prinsip Clean Architecture, repository pattern, atau convention naming yang sudah disepakati di tim engineering Anda.</li>
  <li><strong>Menghasilkan Test Coverage Komprehensif:</strong> Menuntun model untuk mengenali boundary edge cases alih-alih hanya menguji skenario ideal (happy path).</li>
</ul>

<h2>Komparasi Teknik Prompting untuk Pengembangan Perangkat Lunak</h2>

<p>Setiap tugas rekayasa perangkat lunak memerlukan pendekatan prompt yang berbeda. Tabel berikut merangkum karakteristik empat teknik utama beserta skenario penggunaannya:</p>

<table border="1" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
  <thead>
    <tr style="background-color: #f1f5f9;">
      <th style="text-align: left;">Metode Prompting</th>
      <th style="text-align: left;">Mekanisme Kerja</th>
      <th style="text-align: left;">Akurasi Logika</th>
      <th style="text-align: left;">Skenario Terbaik</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Zero-Shot Prompting</strong></td>
      <td>Instruksi langsung tanpa contoh sebelumnya.</td>
      <td>Sedang</td>
      <td>Pertanyaan sintaks dasar, konversi format data sederhana (JSON ke CSV).</td>
    </tr>
    <tr>
      <td><strong>Few-Shot Prompting</strong></td>
      <td>Menyediakan 1-3 contoh pasangan input dan output kode yang diharapkan.</td>
      <td>Tinggi</td>
      <td>Unit test generation, transformasi skema database, formatting data kustom.</td>
    </tr>
    <tr>
      <td><strong>Chain-of-Thought (CoT)</strong></td>
      <td>Meminta model menguraikan langkah penalaran sebelum menulis kode.</td>
      <td>Sangat Tinggi</td>
      <td>Algoritma kompleks, optimasi kompleksitas waktu O(N), debugging bug tersembunyi.</td>
    </tr>
    <tr>
      <td><strong>Role & Constraint Prompting</strong></td>
      <td>Menetapkan persona spesifik (misal: Senior Rust Dev) disertai daftar larangan ketat.</td>
      <td>Tinggi</td>
      <td>Code review keamanan, audit performa, arsitektur microservices.</td>
    </tr>
  </tbody>
</table>

<h2>Framework C-R-E-A-T-E: Struktur Prompt Standar Industri</h2>

<p>Untuk menghindari prompt yang berantakan, gunakan formula C-R-E-A-T-E saat berkomunikasi dengan asisten coding AI Anda:</p>

<ol>
  <li><strong>Context (Konteks):</strong> Jelaskan teknologi stack, versi bahasa pemrograman, dan framework yang digunakan dalam proyek.</li>
  <li><strong>Role (Peran):</strong> Tetapkan persona spesialis teknis (misal: Staff Backend Engineer spesialis PostgreSQL).</li>
  <li><strong>Expectation (Ekspektasi):</strong> Definisikan hasil akhir yang diinginkan secara detail dan terukur.</li>
  <li><strong>Action (Tindakan):</strong> Sebutkan tugas spesifik (refactor, tulis unit test, profiling performa).</li>
  <li><strong>Template (Format Output):</strong> Tentukan format keluaran (misal: hanya blok kode tanpa komentar pembuka, atau format JSON skema tertentu).</li>
  <li><strong>Exclusions (Larangan/Batasan):</strong> Buat daftar tegas apa saja yang tidak boleh diubah atau library eksternal yang dilarang dipakai.</li>
</ol>

<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&auto=format&fit=crop&q=80" alt="Diagram arsitektur kode dan rekayasa data untuk implementasi prompt engineering" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  <figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">Penerapan struktur kontekstual meminimalisir kesalahan interpretasi logika pada model bahasa kecerdasan buatan.</figcaption>
</figure>

<h2>5 Tips Praktis Rekayasa Prompt untuk Keseharian Software Engineer</h2>

<h3>1. Selalu Definisikan Versi Stack dan Runtime Secara Eksplisit</h3>
<p>Seringkali developer hanya menulis: "Buatkan middleware autentikasi di Node.js". Model AI berpotensi menggunakan Express versi lama atau sintaks CommonJS padahal proyek Anda memakai ESM dan Node.js versi 20+.</p>

<p>Perhatikan contoh perbaikan prompt berikut:</p>

<pre><code>// Prompt Kurang Tepat:
Buat middleware auth JWT di Express.

// Prompt Teroptimasi:
Anda adalah Senior Node.js Backend Engineer.
Tulis middleware autentikasi JWT untuk Express.js v4.19+ menggunakan Node.js 20 LTS (ES Modules format: import/export).
Batasan:
- Gunakan library 'jose' atau 'jsonwebtoken' terbaru.
- Ekstrak token dari header Authorization dengan format Bearer.
- Jika token tidak valid atau kedaluwarsa, kembalikan HTTP status 401 dengan JSON respons { success: false, message: 'Unauthorized' }.
- Kembalikan hanya kode TypeScript yang valid tanpa teks basa-basi pembuka.
</code></pre>

<h3>2. Manfaatkan Pola Chain-of-Thought untuk Debugging Kasus Sulit</h3>
<p>Ketika menemukan bug yang sulit dipahami atau race condition di database, jangan langsung meminta solusi instan. Instruksikan model untuk menganalisis akar masalah secara sistematis sebelum menulis sebaris kode perbaikan.</p>

<pre><code>Contoh Prompt Debugging Sistematis:
Berikut adalah potongan kode TypeScript service payment beserta error log stack trace yang muncul di production.

Lakukan langkah-langkah berikut secara berurutan:
1. Analisis alur eksekusi asinkron pada fungsi processTransaction().
2. Identifikasi potensi unhandled promise rejection atau deadlock transaksi database.
3. Jelaskan akar masalah (root cause) dalam 2 paragraf singkat.
4. Sajikan patch kode yang telah diperbaiki dengan penanganan error komprehensif.
</code></pre>

<h3>3. Gunakan Teknik Few-Shot untuk Menyeragamkan Skema Test</h3>
<p>Menulis unit test repetitive sering menghabiskan waktu. Dengan few-shot prompting, Anda cukup memberikan satu contoh test case yang sudah sesuai standar tim, lalu biarkan model membuat test case untuk fungsi-fungsi lainnya.</p>

<pre><code>Contoh Few-Shot Prompt untuk Jest Unit Testing:
Tuliskan unit test menggunakan Jest untuk fungsi calculateDiscount(price, userTier).

Berikut adalah gaya penulisan unit test yang wajib Anda tiru:

describe('calculateTax', () => {
  it('harus menghitung pajak 11% untuk tier reguler', () => {
    const result = calculateTax(100000, 'regular');
    expect(result).toBe(11000);
  });

  it('harus melempar TypeError jika input harga negatif', () => {
    expect(() => calculateTax(-50, 'regular')).toThrow(TypeError);
  });
});

Sekarang, buatkan 4 test cases serupa untuk calculateDiscount dengan skenario edge cases (tier null, diskon melebihi 100%, dan harga 0).
</code></pre>

<h3>4. Terapkan Delimiter Pembatas Input Kode</h3>
<p>Gunakan tanda pemisah yang jelas seperti triple backticks (```) atau tag XML (&lt;code&gt; &lt;/code&gt;) saat menyertakan potongan file kode sumber ke dalam prompt. Delimiter membantu LLM memisahkan mana teks instruksi dan mana data mentah yang harus dianalisis.</p>

<h3>5. Tuntut Output Terstruktur (JSON Schema atau Diff Format)</h3>
<p>Jika Anda mengintegrasikan hasil prompt ke dalam pipeline script otomatis atau CI/CD, mintalah respon dalam skema JSON baku. Hindari respon deskriptif naratif yang sulit diparsing oleh mesin.</p>

<pre><code>Format Respons Wajib:
Kembalikan analisis keamanan dalam skema JSON berikut tanpa blok markdown tambahan:
{
  "vulnerability_level": "HIGH" | "MEDIUM" | "LOW",
  "issue_title": string,
  "line_number": number,
  "recommendation": string
}
</code></pre>

<h2>Rekomendasi Praktis untuk Alur Kerja Engineering Harian</h2>

<p>Mengintegrasikan prompt engineering ke dalam alur kerja harian bukanlah tentang menghafal rumus, melainkan membangun kebiasaan berkomunikasi secara terstruktur. Simpan kumpulan prompt template yang telah teruji (prompt snippet) di dalam repository internal tim Anda, misalnya dalam folder <code>.github/prompts/</code> atau file markdown terpusat.</p>

<p>Dengan standardisasi ini, seluruh anggota tim developer dapat menghasilkan standar kualitas kode yang seragam, mempercepat proses code review, serta memangkas waktu onboarding anggota baru secara signifikan.</p>

<div class="faq-section">
  <h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>
  
  <h3>Apa perbedaan utama prompt engineering software engineer dengan pengguna awam?</h3>
  <p>Software engineer menuntut determinisme logika, kepatuhan arsitektur, dan penanganan edge cases yang ketat, sedangkan pengguna awam biasanya hanya membutuhkan jawaban konseptual atau teks deskriptif umum.</p>
  
  <h3>Apakah prompt engineering akan menggantikan kemampuan coding dasar?</h3>
  <p>Tidak. Prompt engineering justru membutuhkan pemahaman fundamental coding yang kuat agar Anda dapat memvalidasi kebenaran logika kode, mendeteksi bug keamanan tersembunyi, dan memastikan efisiensi algoritma yang dihasilkan AI.</p>
  
  <h3>Bagaimana cara terbaik mencegah AI menghasilkan library usang?</h3>
  <p>Sebutkan versi spesifik framework dan runtime Anda di awal prompt (misalnya React 19, Next.js 15 App Router, Python 3.12) serta cantumkan larangan tegas terhadap library yang sudah deprecated.</p>
</div>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Apa perbedaan utama prompt engineering software engineer dengan pengguna awam?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Software engineer menuntut determinisme logika, kepatuhan arsitektur, dan penanganan edge cases yang ketat, sedangkan pengguna awam biasanya hanya membutuhkan jawaban konseptual atau teks deskriptif umum."
      }
    },
    {
      "@type": "Question",
      "name": "Apakah prompt engineering akan menggantikan kemampuan coding dasar?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Tidak. Prompt engineering justru membutuhkan pemahaman fundamental coding yang kuat agar Anda dapat memvalidasi kebenaran logika kode, mendeteksi bug keamanan tersembunyi, dan memastikan efisiensi algoritma yang dihasilkan AI."
      }
    },
    {
      "@type": "Question",
      "name": "Bagaimana cara terbaik mencegah AI menghasilkan library usang?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Sebutkan versi spesifik framework dan runtime Anda di awal prompt (misalnya React 19, Next.js 15 App Router, Python 3.12) serta cantumkan larangan tegas terhadap library yang sudah deprecated."
      }
    }
  ]
}
</script>'''

# Hitung jumlah kata
text_only = re.sub(r'<[^>]+>', ' ', html_content)
words = [w for w in text_only.split() if w.strip()]
word_count = len(words)
print(f"Word count: {word_count}")

# Validasi constraints
forbidden_phrases = [
    'di era digital', 'seperti yang kita tahu', 'perkembangan teknologi saat ini',
    'dalam dunia teknologi', 'tentu saja', 'tak dapat dipungkiri', 'pada dasarnya',
    'klik di sini', 'baca di sini'
]
for phrase in forbidden_phrases:
    if phrase in html_content.lower():
        print(f"WARNING: Forbidden phrase found: '{phrase}'")

if '<h2>kesimpulan</h2>' in html_content.lower() or '<h2>penutup</h2>' in html_content.lower():
    print("WARNING: Forbidden conclusion heading found!")

assert 'https://bagustechnologia.blogspot.com/2026/10/rekomendasi-ai-coding-assistant-gratis.html' in html_content, 'Internal link missing'
assert '<table' in html_content, 'Table missing'
assert '<figure' in html_content, 'Figure missing'
assert 'FAQPage' in html_content, 'FAQ Schema missing'

# Simpan ke SQLite
conn = sqlite3.connect('/opt/data/blogger-agent/data.db')
cur = conn.cursor()

# Update keyword status
cur.execute("UPDATE keywords SET status = 'in_progress' WHERE id = 5")

# Insert artikel draft
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
labels = 'Artificial Intelligence, Software Engineering, Productivity, Coding, Web Development'
blog_id = '2940095957137948013'

cur.execute('''
    INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, status, created_at, updated_at, blog_id)
    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
''', (title, target_keyword, meta_desc, html_content, labels, now_str, now_str, blog_id))

new_article_id = cur.lastrowid
conn.commit()

print(f"Article saved with ID: {new_article_id}")
print("Keyword updated:", cur.execute("SELECT * FROM keywords WHERE id = 5").fetchone())
print("Article row:", cur.execute("SELECT id, title, target_keyword, status, blog_id, created_at FROM articles WHERE id = ?", (new_article_id,)).fetchone())

conn.close()
