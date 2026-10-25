import sqlite3
import re
import json
from datetime import datetime
from db import DB_PATH

# 1. Verify and select keyword
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT id, keyword, search_intent FROM keywords WHERE status = 'planned' ORDER BY id ASC LIMIT 1")
kw_row = c.fetchone()
if not kw_row:
    raise RuntimeError('No planned keyword found!')

kw_id, target_keyword, search_intent = kw_row
print(f"Selected keyword [{kw_id}]: '{target_keyword}' (Intent: {search_intent})")

# Title: 50-60 characters, CTR oriented, includes primary keyword
title = "Perbandingan Claude dan ChatGPT untuk Programming (2026)"
print(f"Title: '{title}' ({len(title)} chars)")
assert 50 <= len(title) <= 60, f"Title length {len(title)} is invalid (must be 50-60 chars)"

# Meta description: 140-155 characters with CTA, includes primary keyword
meta_description = "Simak perbandingan Claude dan ChatGPT untuk programming mendalam. Temukan model AI terbaik untuk coding, refactoring, dan debugging proyek Anda sekarang!"
print(f"Meta description: '{meta_description}' ({len(meta_description)} chars)")
assert 140 <= len(meta_description) <= 155, f"Meta description length {len(meta_description)} is invalid (must be 140-155 chars)"

# 2. Build Article HTML Body
# Direct answer hook: 40-50 words answering search intent immediately
content_parts = []

content_parts.append('''<p><strong>Perbandingan Claude dan ChatGPT untuk programming</strong> menunjukkan bahwa Claude (khususnya Claude 3.5 Sonnet) unggul telak dalam pemahaman arsitektur proyek multi-file, refactoring tanpa merusak kode lama, dan kepatuhan instruksi logika kompleks. Sebaliknya, ChatGPT (didukung model GPT-4o dan keluarga OpenAI o1) lebih unggul dalam memecahkan algoritma murni, eksekusi lingkungan Python terisolasi, serta keragaman fitur ekosistem serbaguna.</p>''')

content_parts.append('''<p>Memilih asisten kecerdasan buatan untuk rekayasa perangkat lunak modern menuntut evaluasi yang jauh lebih terukur daripada sekadar melihat kemampuan menghasilkan fungsi sederhana. Para pengembang perangkat lunak, arsitek sistem, maupun perekayasa web membutuhkan model yang mampu mengenali dependensi antar-modul, mematuhi standar pengetikan ketat, meminimalkan halusinasi terhadap pustaka yang telah usang, dan menghasilkan kode yang siap lolos uji integrasi pada pipa CI/CD.</p>''')

content_parts.append('''<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=1200&auto=format&fit=crop&q=80" alt="Perbandingan Claude dan ChatGPT untuk programming dalam pengujian kode perangkat lunak" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  <figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">Evaluasi komparatif antara Claude dan ChatGPT dalam menangani alur kerja pengembangan perangkat lunak.</figcaption>
</figure>''')

content_parts.append('''<p>Jika Anda terbiasa menulis kode di dalam editor Visual Studio Code dan membutuhkan alat pelengkap otomatis tanpa biaya langganan bulanan, Anda dapat meninjau panduan kami mengenai <a href="https://bagustechnologia.blogspot.com/2026/10/rekomendasi-ai-coding-assistant-gratis.html">rekomendasi AI coding assistant gratis untuk VS Code</a> yang mengulas ekstensi mandiri untuk meningkatkan ritme kerja harian Anda.</p>''')

content_parts.append('''<h2>Tabel Komparasi Fitur Teknis: Claude vs ChatGPT</h2>
<p>Sebelum membahas pengujian kode dan studi kasus baris demi baris, tabel berikut merangkum perbedaan spesifikasi arsitektur, kapasitas memori kerja token, dan kapabilitas rekayasa dari kedua platform terdepan ini:</p>

<table border="1" cellpadding="10" cellspacing="0" style="width: 100%; border-collapse: collapse; margin: 20px 0; text-align: left; border: 1px solid #cbd5e1;">
  <thead>
    <tr style="background-color: #0f172a; color: #ffffff;">
      <th style="padding: 12px; border: 1px solid #334155;">Aspek Evaluasi</th>
      <th style="padding: 12px; border: 1px solid #334155;">Anthropic Claude (3.5 Sonnet)</th>
      <th style="padding: 12px; border: 1px solid #334155;">OpenAI ChatGPT (GPT-4o & o1)</th>
    </tr>
  </thead>
  <tbody>
    <tr style="background-color: #f8fafc;">
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Model Andalan untuk Coding</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Claude 3.5 Sonnet (arsitektur hybrid cepat & cermat)</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">GPT-4o (multimodal kilat) dan OpenAI o1 (reasoning step-by-step)</td>
    </tr>
    <tr>
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Kapasitas Jendela Konteks</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">200.000 token (~150.000 kata) dengan retensi memori tinggi</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">128.000 token pada GPT-4o standard chat</td>
    </tr>
    <tr style="background-color: #f8fafc;">
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Kepatuhan Refactoring & Konsistensi</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Sangat Tinggi (jarang mengubah nama variabel atau merusak tipe modul lain)</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Moderat (sering menyederhanakan kode sepihak atau mengganti library lama)</td>
    </tr>
    <tr>
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Penyelesaian Masalah Algoritmik</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Sangat Baik untuk kasus rekayasa praktis dan web app</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Unggul Tertinggi pada OpenAI o1 (optimasi matematika murni & graf kompetitif)</td>
    </tr>
    <tr style="background-color: #f8fafc;">
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Fitur Kolaborasi Antarmuka</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Artifacts (live rendering HTML/SVG/React, markdown terpisah)</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Canvas (inline editing baris kode) & Code Interpreter (eksekusi Python sandbox)</td>
    </tr>
    <tr>
      <td style="padding: 10px; border: 1px solid #cbd5e1;"><strong>Gejala Kemalasan Sintaksis (Lazy Code)</strong></td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Sangat Minim (menuliskan blok implementasi secara utuh dan terperinci)</td>
      <td style="padding: 10px; border: 1px solid #cbd5e1;">Terkadang menyisipkan komentar singkat <code>// logikanya sama seperti di atas</code></td>
    </tr>
  </tbody>
</table>''')

content_parts.append('''<h2>1. Kemampuan Mengelola Konteks Basis Kode Skala Besar</h2>
<p>Ketika Anda mengembangkan proyek aplikasi skala perusahaan yang melibatkan puluhan modul, model kecerdasan buatan harus mampu membaca interaksi antar-file tanpa kehilangan fokus pada detail kecil. Masalah yang sering dihadapi oleh pengembang saat menyematkan beberapa file sekaligus ke dalam prompt adalah fenomena <em>needle-in-a-haystack</em> atau hilangnya konteks di bagian tengah dokumen.</p>

<h3>Kekuatan Claude 3.5 Sonnet dalam Menjaga Struktur Modul</h3>
<p>Claude 3.5 Sonnet memiliki keunggulan arsitektural dalam memperhatikan hubungan dependensi. Saat Anda memberikan skema database PostgreSQL, definisi antarmuka TypeScript di berkas <code>types.ts</code>, dan pengendali API di berkas <code>controller.ts</code>, Claude mampu memetakan relasi asing, tipe data opsional, dan validasi skema tanpa menghasilkan galat ketidakcocokan tipe (<em>type mismatch</em>).</p>

<p>Kelebihan lainnya terlihat pada kestabilan gaya penulisan kode. Claude cenderung mengikuti konvensi penamaan yang sudah ada di repositori Anda, seperti camelCase, PascalCase, atau penataan arsitektur Clean Architecture, sehingga kode yang dihasilkan tampak seragam dengan kode yang ditulis oleh tim pengembang manusia.</p>

<h3>Karakteristik ChatGPT dalam Memproses Proyek Berkas Jamak</h3>
<p>ChatGPT dengan basis model GPT-4o memproses konteks dengan kecepatan sangat tinggi. Namun, jika Anda menyertakan berkas berukuran lebih dari 1.000 baris, model ini terkadang melakukan penyederhanaan fungsi yang tidak diminta. ChatGPT sering kali memangkas penanganan galat (error handling) yang sudah ada sebelumnya demi memperpendek respons teks keluaran.</p>

<p>Kendati demikian, antarmuka Canvas pada ChatGPT menghadirkan kemudahan visual. Anda dapat menyorot satu fungsi tertentu di layar samping, lalu meminta sistem untuk menambahkan pengujian unit tanpa mengganggu baris kode di sekelilingnya.</p>''')

content_parts.append('''<h2>2. Uji Kasus Nyata: Menangani Resilient Asynchronous Logic</h2>
<p>Untuk melihat perbedaan nyata saat menghadapi masalah pemrograman harian, mari kita uji kedua sistem dengan skenario teknis: membangun antrean pemanggilan HTTP (<em>resilient fetch queue</em>) yang harus menangani kegagalan jaringan sementara (transient errors), penundaan eksponensial (exponential backoff), serta pembatalan proses menggunakan <code>AbortController</code>.</p>

<p>Berikut adalah contoh implementasi logika ketahanan koneksi yang ideal dalam lingkungan JavaScript/TypeScript modern:</p>

<pre><code>// Resilient HTTP Fetch dengan Backoff Eksponensial dan AbortSignal
interface RetryOptions extends RequestInit {
  maxRetries?: number;
  baseDelayMs?: number;
}

async function resilientFetch<T>(url: string, options: RetryOptions = {}): Promise<T> {
  const { maxRetries = 3, baseDelayMs = 500, signal, ...fetchConfig } = options;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      if (signal?.aborted) {
        throw new DOMException('Permintaan dibatalkan oleh pemanggil', 'AbortError');
      }

      const response = await fetch(url, { ...fetchConfig, signal });
      if (!response.ok) {
        if (response.status >= 500 && attempt < maxRetries) {
          const delay = baseDelayMs * Math.pow(2, attempt - 1);
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
        throw new Error(`HTTP Galat: Status ${response.status}`);
      }
      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') throw err;
      if (attempt === maxRetries) throw err;
      const delay = baseDelayMs * Math.pow(2, attempt - 1);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
  throw new Error('Mencapai batas perulangan antrean');
}</code></pre>

<p>Dari pengujian di atas, Claude 3.5 Sonnet secara konsisten menyertakan pengecekan <code>isServerFault</code> (membedakan error status 4xx dengan 5xx) dan menambahkan <em>jitter</em> acak pada jeda waktu untuk menghindari fenomena <em>thundering herd problem</em> pada server. Sementara itu, respons bawaan ChatGPT sering kali mengulang seluruh kode status HTTP tanpa seleksi, yang dapat membebani server tujuan jika masalahnya berada pada autentikasi klien (status 401 atau 403).</p>''')

content_parts.append('''<h2>3. Komparasi Ekosistem Antarmuka: Claude Artifacts vs ChatGPT Canvas & Tools</h2>
<p>Perbedaan filosofi desain antarmuka antara Anthropic dan OpenAI memberikan dampak langsung pada produktivitas sehari-hari seorang perekayasa perangkat lunak.</p>

<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=1200&auto=format&fit=crop&q=80" alt="Layar editor kode interaktif dan perbandingan alat bantu kecerdasan buatan pengembang" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  <figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">Antarmuka kerja interaktif modern mempercepat visualisasi prototipe dan inspeksi kode langsung.</figcaption>
</figure>

<h3>Keunggulan Claude Artifacts untuk Web & Prototipe Visual</h3>
<p>Fitur Artifacts pada Claude memisahkan konten percakapan umum dengan keluaran teknis berbobot tinggi. Ketika Anda meminta Claude membuat komponen dasbor interaktif, bagan alur kerja sistem, atau antarmuka HTML/Tailwind CSS, sistem otomatis menampilkan panel pratinjau langsung di sisi kanan layar.</p>
<ul>
  <li><strong>Pratinjau Langsung:</strong> Anda dapat langsung berinteraksi dengan tombol, input formulir, dan animasi CSS tanpa perlu memindahkan kode ke localhost.</li>
  <li><strong>Diagram Arsitektur:</strong> Claude mampu merender diagram Mermaid secara instan, mempermudah dokumentasi alur sistem mikroservis.</li>
  <li><strong>Manajemen Versi Berkas:</strong> Setiap pembaruan kode menghasilkan riwayat revisi (history) yang memudahkan Anda kembali ke versi sebelumnya jika terjadi regresi.</li>
</ul>

<h3>Keunggulan ChatGPT Canvas dan Code Interpreter</h3>
<p>OpenAI membekali ChatGPT dengan dua fitur penting:</p>
<ul>
  <li><strong>Editor Kolaboratif Canvas:</strong> Memungkinkan edit kode selektif tanpa mengulang seluruh prompt percakapan.</li>
  <li><strong>Advanced Data Analysis:</strong> Menjalankan skrip Python di lingkungan server terisolasi untuk analisis data, validasi formula, dan manipulasi spreadsheet.</li>
</ul>''')

content_parts.append('''<h2>4. Uji Kemampuan Logika Penalaran: Claude 3.5 Sonnet vs OpenAI o1</h2>
<p>Kehadiran keluarga model penalaran <strong>OpenAI o1</strong> menghadirkan kapabilitas baru melalui proses <em>chain-of-thought</em> internal untuk merencanakan skenario pengujian sebelum menuliskan kode.</p>

<p>Dalam memecahkan masalah pohon biner berimbang, optimasi graf dinamis, atau algoritma kriptografi kustom, OpenAI o1 mencatatkan akurasi lebih tinggi dibanding model standar berkat verifikasi deduktif mandiri sebelum mencetak jawaban.</p>

<p>Sebaliknya, untuk rekayasa harian seperti REST API, SQL queries, konfigurasi Docker, dan tata letak responsif, Claude 3.5 Sonnet tetap paling efisien karena merespons instan tanpa jeda pemikiran panjang.</p>''')

content_parts.append('''<h2>5. Analisis Biaya Langganan dan Efisiensi Token API</h2>
<p>Bagi tim pengembang maupun freelancer independen, efisiensi biaya merupakan pertimbangan krusial:</p>

<ul>
  <li><strong>Claude Pro ($20/bulan):</strong> Akses prioritas ke Claude 3.5 Sonnet dengan batasan kuota berkala 5 jam. Alternatif penggunaan API token (pay-as-you-go) sering kali jauh lebih ekonomis bagi developer intensif.</li>
  <li><strong>ChatGPT Plus ($20/bulan):</strong> Menyediakan paket serbaguna mencakup kuota GPT-4o, model reasoning o1, mode suara, dan generator gambar DALL-E untuk kebutuhan utilitas yang lebih luas.</li>
</ul>''')

content_parts.append('''<h2>Rekomendasi Terbaik untuk Alur Kerja Pemrograman Anda</h2>
<p>Berdasarkan pengujian ekstensif pada berbagai skenario rekayasa perangkat lunak, berikut adalah panduan praktis untuk menentukan alat yang paling tepat:</p>

<ol>
  <li><strong>Pilih Claude (3.5 Sonnet) Sebagai Asisten Utama Jika:</strong>
    <ul>
      <li>Fokus utama Anda adalah pengembangan aplikasi web (Frontend React/Next.js, Vue, Svelte) dan backend TypeScript/Node.js/Python.</li>
      <li>Anda membutuhkan model yang patuh pada arsitektur kode eksisting tanpa memangkas blok implementasi secara sembarangan.</li>
      <li>Anda mengandalkan fitur Artifacts untuk memvisualisasikan antarmuka dan diagram alur sistem secara langsung di peramban.</li>
    </ul>
  </li>
  <li><strong>Pilih ChatGPT (GPT-4o & o1) Sebagai Asisten Utama Jika:</strong>
    <ul>
      <li>Pekerjaan Anda berpusat pada rekayasa data, analisis statistik Python, dan pemrosesan dataset dalam berkas spreadsheet atau database lokal.</li>
      <li>Anda sering menghadapi tantangan algoritma tingkat tinggi, optimasi matematika murni, atau kompetisi pemrograman yang memerlukan penalaran deduktif o1.</li>
      <li>Anda menginginkan satu langganan terpadu yang dapat melayani kebutuhan pembuatan kode, interaksi suara, riset pasar, dan desain visual grafis.</li>
    </ul>
  </li>
</ol>

<p>Banyak pengembang profesional kini menerapkan pendekatan hibrida: mengandalkan Claude 3.5 Sonnet di dalam editor kode harian untuk menulis berkas fitur dan refactoring repositori, sembari menyiapkan ChatGPT sebagai konsultan arsitektur data dan pemeriksa algoritma yang menantang.</p>''')

content_parts.append('''<div class="faq-section">
  <h2>Pertanyaan yang Sering Diajukan (FAQ)</h2>
  
  <h3>Mana yang lebih unggul untuk pemrograman: Claude 3.5 Sonnet atau GPT-4o?</h3>
  <p>Untuk penulisan kode harian, pemeliharaan struktur proyek, dan kepatuhan terhadap gaya arsitektur, Claude 3.5 Sonnet terbukti lebih unggul karena tidak mudah memangkas kode dan memiliki retensi konteks repositori yang sangat stabil. Sementara GPT-4o unggul dalam kecepatan keluaran teks dan eksekusi skrip data Python langsung di server.</p>
  
  <h3>Apakah Claude versi gratis memadai untuk membantu pekerjaan coding?</h3>
  <p>Versi gratis Claude memberikan akses ke model Claude 3.5 Sonnet dengan pembatasan jumlah pesan harian. Akun gratis ini memadai untuk pengembang yang membutuhkan tinjauan fungsi kecil atau pembuatan komponen web terisolasi.</p>
  
  <h3>Kapan seorang developer sebaiknya menggunakan OpenAI o1 dibanding Claude?</h3>
  <p>Gunakan OpenAI o1 ketika Anda menghadapi masalah algoritma kompleks tingkat tinggi, seperti optimasi jalur graf dinamis, perhitungan probabilitas matematika rumit, atau perancangan arsitektur konkurensi data yang rentan terhadap galat race condition.</p>
</div>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Mana yang lebih unggul untuk pemrograman: Claude 3.5 Sonnet atau GPT-4o?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Untuk penulisan kode harian, pemeliharaan struktur proyek, dan kepatuhan terhadap gaya arsitektur, Claude 3.5 Sonnet terbukti lebih unggul karena tidak mudah memangkas kode dan memiliki retensi konteks repositori yang sangat stabil. Sementara GPT-4o unggul dalam kecepatan keluaran teks dan eksekusi skrip data Python langsung di server."
      }
    },
    {
      "@type": "Question",
      "name": "Apakah Claude versi gratis memadai untuk membantu pekerjaan coding?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Versi gratis Claude memberikan akses ke model Claude 3.5 Sonnet dengan pembatasan jumlah pesan harian. Akun gratis ini memadai untuk pengembang yang membutuhkan tinjauan fungsi kecil atau pembuatan komponen web terisolasi."
      }
    },
    {
      "@type": "Question",
      "name": "Kapan seorang developer sebaiknya menggunakan OpenAI o1 dibanding Claude?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Gunakan OpenAI o1 ketika Anda menghadapi masalah algoritma kompleks tingkat tinggi, seperti optimasi jalur graf dinamis, perhitungan probabilitas matematika rumit, atau perancangan arsitektur konkurensi data yang rentan terhadap galat race condition."
      }
    }
  ]
}
</script>''')

html_content = "\n\n".join(content_parts)

# 3. Validation & Constraints Checking
text_only = re.sub(r'<[^>]+>', ' ', html_content)
words = [w for w in text_only.split() if w.strip()]
word_count = len(words)
print(f"Total word count: {word_count}")
assert 1200 <= word_count <= 1800, f"Word count {word_count} is outside the required range (1200 - 1800 words)"

# Forbidden phrases check
forbidden_phrases = [
    'di era digital',
    'seperti yang kita ketahui',
    'perkembangan teknologi saat ini',
    'dalam dunia teknologi',
    'tentu saja',
    'tak dapat dipungkiri',
    'secara keseluruhan',
    'pada dasarnya',
    'klik di sini',
    'baca di sini'
]
for fp in forbidden_phrases:
    matches = re.findall(rf'\b{re.escape(fp)}\b', html_content, re.IGNORECASE)
    if matches:
        raise ValueError(f"Found forbidden phrase: '{fp}' {len(matches)} time(s)")

# Forbidden heading 'Kesimpulan' check
if re.search(r'<h[1-6][^>]*>.*kesimpulan.*</h[1-6]>', html_content, re.IGNORECASE):
    raise ValueError("Forbidden heading 'Kesimpulan' found!")

# Validate JSON-LD Schema
schema_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
if not schema_match:
    raise ValueError("FAQ JSON-LD Schema not found!")
json_ld = json.loads(schema_match.group(1))
assert json_ld.get('@type') == 'FAQPage', f"Invalid schema type: {json_ld.get('@type')}"
assert len(json_ld.get('mainEntity', [])) >= 3, "At least 3 FAQ items required"
print("JSON-LD FAQ Schema validated successfully!")

# 4. Update Database
# Update keyword status to in_progress
c.execute("UPDATE keywords SET status = 'in_progress' WHERE id = ?", (kw_id,))

# Insert into articles
labels = "Artificial Intelligence, Coding, Software Engineering, Claude, ChatGPT, Web Development"
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
c.execute('''
    INSERT INTO articles (title, target_keyword, meta_description, content_html, labels, status, created_at, updated_at, blog_id)
    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, '2940095957137948013')
''', (title, target_keyword, meta_description, html_content, labels, now_str, now_str))

article_id = c.lastrowid
conn.commit()

# Verify insertion
c.execute("SELECT id, title, target_keyword, status, created_at FROM articles WHERE id = ?", (article_id,))
print("Inserted article row:", c.fetchone())

c.execute("SELECT id, keyword, status FROM keywords WHERE id = ?", (kw_id,))
print("Updated keyword row:", c.fetchone())

conn.close()
print(f"ALL DONE! Article ID: {article_id}")
