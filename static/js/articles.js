// --- Blogger Auto-Pilot: Article Editor, Audits & Publishing ---
    async function loadData() {
      try {
        const blogParam = activeBlog ? `?blog_id=${activeBlog.id}` : '';
        const [resArt, resKw] = await Promise.all([
          fetch('/api/articles' + blogParam),
          fetch('/api/keywords' + blogParam)
        ]);
        articles = await resArt.json();
        keywords = await resKw.json();
        
        const countBadge = document.getElementById('article-count-badge');
        if (countBadge) countBadge.innerText = articles.length + ' Draf';
        
        renderArticles();
        renderKeywords();
      } catch (err) {
        console.error('Error loading data:', err);
      }
    }

    let currentArticleFilter = 'all';
    let currentSearchQuery = '';

    function setArticleFilter(filter) {
      currentArticleFilter = filter;
      const btnAll = document.getElementById('filter-art-all');
      const btnDraft = document.getElementById('filter-art-draft');
      const btnReview = document.getElementById('filter-art-review');
      const btnBlogger = document.getElementById('filter-art-blogger');
      const btnPub = document.getElementById('filter-art-published');

      [btnAll, btnDraft, btnReview, btnBlogger, btnPub].forEach(b => {
        if (b) b.className = "px-2.5 py-1 rounded-lg font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition";
      });

      if (filter === 'all' && btnAll) btnAll.className = "px-2.5 py-1 rounded-lg font-semibold bg-brand-600 text-white shadow-sm transition";
      if (filter === 'draft' && btnDraft) btnDraft.className = "px-2.5 py-1 rounded-lg font-semibold bg-amber-600 text-white shadow-sm transition";
      if (filter === 'review' && btnReview) btnReview.className = "px-2.5 py-1 rounded-lg font-semibold bg-indigo-600 text-white shadow-sm transition";
      if (filter === 'blogger_draft' && btnBlogger) btnBlogger.className = "px-2.5 py-1 rounded-lg font-semibold bg-sky-600 text-white shadow-sm transition";
      if (filter === 'published' && btnPub) btnPub.className = "px-2.5 py-1 rounded-lg font-semibold bg-emerald-600 text-white shadow-sm transition";

      renderArticles();
    }

    function handleArticleSearch(query) {
      currentSearchQuery = (query || '').toLowerCase().trim();
      renderArticles();
    }

    function renderArticles() {
      const list = document.getElementById('articles-list');
      
      const draftCount = (articles || []).filter(a => a.status === 'draft').length;
      const reviewCount = (articles || []).filter(a => a.status === 'pending_review' || a.status === 'approved').length;
      const bloggerCount = (articles || []).filter(a => a.status === 'blogger_draft').length;
      const pubCount = (articles || []).filter(a => a.status === 'published').length;
      const totalCount = (articles || []).length;

      // Update Metric Strip
      const elStatDraft = document.getElementById('stat-draft-count');
      const elStatBlogger = document.getElementById('stat-blogger-draft-count');
      const elStatPub = document.getElementById('stat-published-count');
      const elCountAll = document.getElementById('count-all');
      const elCountDraft = document.getElementById('count-draft');
      const elCountReview = document.getElementById('count-review');
      const elCountBlogger = document.getElementById('count-blogger');
      const elCountPub = document.getElementById('count-published');
      const elBadge = document.getElementById('article-count-badge');

      if (elStatDraft) elStatDraft.innerText = draftCount;
      if (elStatBlogger) elStatBlogger.innerText = bloggerCount;
      if (elStatPub) elStatPub.innerText = pubCount;
      if (elCountAll) elCountAll.innerText = totalCount;
      if (elCountDraft) elCountDraft.innerText = draftCount;
      if (elCountReview) elCountReview.innerText = reviewCount;
      if (elCountBlogger) elCountBlogger.innerText = bloggerCount;
      if (elCountPub) elCountPub.innerText = pubCount;
      if (elBadge) elBadge.innerText = `${totalCount} Artikel`;

      if (!articles || !articles.length) {
        list.innerHTML = `
          <div class="text-center py-16 border border-dashed border-slate-300 dark:border-slate-800 rounded-2xl p-6">
            <div class="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 flex items-center justify-center mx-auto mb-3 font-bold text-lg">✍️</div>
            <p class="text-slate-800 dark:text-slate-200 font-semibold text-sm">Belum ada antrean draf artikel</p>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">Klik <b>Buat Draf AI</b> atau <b>Tulis Manual</b> untuk memulai publikasi konten baru.</p>
          </div>
        `;
        return;
      }

      // Filter articles
      let filtered = articles.slice();
      if (currentArticleFilter === 'review') {
        filtered = filtered.filter(a => a.status === 'pending_review' || a.status === 'approved');
      } else if (currentArticleFilter !== 'all') {
        filtered = filtered.filter(a => a.status === currentArticleFilter);
      }

      if (currentSearchQuery) {
        filtered = filtered.filter(a => 
          (a.title || '').toLowerCase().includes(currentSearchQuery) ||
          (a.target_keyword || '').toLowerCase().includes(currentSearchQuery) ||
          (a.meta_description || '').toLowerCase().includes(currentSearchQuery)
        );
      }

      if (!filtered.length) {
        list.innerHTML = `
          <div class="text-center py-12 border border-dashed border-slate-800 rounded-2xl p-6">
            <p class="text-slate-400 text-xs">Tidak ditemukan artikel yang cocok dengan filter atau kata kunci pencarian.</p>
          </div>
        `;
        return;
      }
      
      list.innerHTML = filtered.map(a => {
        const isPublished = a.status === 'published';
        const isBloggerDraft = a.status === 'blogger_draft';
        const isApproved = a.status === 'approved';
        const isPendingReview = a.status === 'pending_review';

        let badge = '';
        if (isPublished) {
          badge = `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>Live di Blogger</span>`;
        } else if (isBloggerDraft) {
          badge = `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30"><span class="w-1.5 h-1.5 rounded-full bg-sky-500"></span>Draft di Blogger</span>`;
        } else if (isApproved) {
          badge = `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30"><span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>✓ Disetujui (Siap Kirim)</span>`;
        } else if (isPendingReview) {
          badge = `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30"><span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>⏳ Menunggu Review</span>`;
        } else {
          badge = `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>Draft Lokal</span>`;
        }

        let workflowBtn = '';
        if (a.status === 'draft') {
          workflowBtn = `<button onclick="updateArticleStatus(${a.id}, 'pending_review')" title="Kirim ke editor untuk direview" class="px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 rounded-lg text-xs font-semibold transition active:scale-95">Minta Review</button>`;
        } else if (a.status === 'pending_review') {
          workflowBtn = `<button onclick="updateArticleStatus(${a.id}, 'approved')" title="Setujui artikel untuk dipublikasikan" class="px-2.5 py-1.5 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 rounded-lg text-xs font-semibold transition active:scale-95">✓ Setujui</button>`;
        }
        
        return `
          <div class="p-4 rounded-xl border border-slate-200 dark:border-slate-800/90 bg-slate-50/80 dark:bg-[#070b14]/70 hover:border-slate-300 dark:hover:border-slate-700/80 transition duration-150 flex flex-col justify-between gap-3 shadow-sm">
            <div class="space-y-2">
              <div class="flex items-center justify-between flex-wrap gap-2">
                ${badge}
                <span class="text-xs text-slate-700 dark:text-slate-300 font-mono bg-white dark:bg-slate-900/80 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-800">KW: ${a.target_keyword || '-'}</span>
              </div>
              <h3 class="font-bold text-slate-900 dark:text-slate-100 text-sm md:text-base leading-snug hover:text-brand-600 dark:hover:text-brand-400 cursor-pointer transition" onclick="viewArticle(${a.id})">${a.title}</h3>
              <p class="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">${a.meta_description || 'Belum ada meta deskripsi'}</p>
              ${a.blogger_url ? `<a href="${a.blogger_url}" target="_blank" class="text-xs text-brand-600 dark:text-brand-400 hover:text-brand-500 dark:hover:text-brand-300 font-medium inline-flex items-center gap-1 hover:underline pt-1">Buka Post Live di Blogger &rarr;</a>` : ''}
            </div>
            <div class="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800/50 flex-wrap">
              <button onclick="deleteArticle(${a.id}, '${(a.title || '').replace(/'/g, "\\'")}')" title="Hapus artikel dari database" class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-red-500/10 transition text-sm font-bold shrink-0">&times;</button>
              <div class="flex items-center gap-2 flex-wrap">
                ${workflowBtn}
                <button onclick="viewArticle(${a.id})" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-semibold transition active:scale-95">Preview / Edit</button>
                <button onclick="quickPublish(${a.id}, true, this)" title="Kirim/Update sebagai Draft online di Blogger" class="px-2.5 py-1.5 bg-amber-600/80 hover:bg-amber-600 text-amber-100 rounded-lg text-xs font-semibold transition active:scale-95 flex items-center gap-1">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
                  <span>Draft</span>
                </button>
                <button onclick="quickPublish(${a.id}, false, this)" title="${isPublished ? 'Perbarui Postingan yang sudah tayang di Blogger' : 'Publikasikan Live ke Blogger'}" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow-sm shadow-emerald-600/20 active:scale-95 flex items-center gap-1">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                  <span>${isPublished ? 'Update Live' : 'Publish Live'}</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }


    function viewArticle(id) {
      const a = articles.find(x => x.id === id);
      if (!a) return;
      document.getElementById('modal-article-id').value = a.id;
      document.getElementById('modal-article-title').value = a.title;
      document.getElementById('modal-article-keyword').value = a.target_keyword || '';
      document.getElementById('modal-article-labels').value = a.labels || '';
      document.getElementById('modal-article-meta').value = a.meta_description || '';
      document.getElementById('modal-article-content').value = a.content_html;
      
      syncModalContent();
      updateCharCount();
      
      const isPublished = a.status === 'published';
      const hasBloggerId = Boolean(a.blogger_post_id);

      const draftBtn = document.getElementById('btn-draft-action');
      if (draftBtn) {
        draftBtn.classList.remove('hidden');
        draftBtn.querySelector('span').innerText = hasBloggerId ? 'Update Draft Blogger' : 'Kirim Draft ke Blogger';
      }

      const publishBtn = document.getElementById('btn-publish-action');
      if (publishBtn) {
        publishBtn.classList.remove('hidden');
        publishBtn.querySelector('span').innerText = isPublished ? 'Perbarui Post Live' : 'Publish Live ke Blogger';
      }

      const reqReviewBtn = document.getElementById('btn-request-review');
      if (reqReviewBtn) {
        if (a.status === 'draft') reqReviewBtn.classList.remove('hidden');
        else reqReviewBtn.classList.add('hidden');
      }

      const approveBtn = document.getElementById('btn-approve-article');
      if (approveBtn) {
        if (a.status === 'pending_review') approveBtn.classList.remove('hidden');
        else approveBtn.classList.add('hidden');
      }
      
      switchModalView('preview');
      updateSerpPreview(a.title, a.meta_description);
      document.body.classList.add('overflow-hidden');
      document.getElementById('article-modal').classList.remove('hidden');
    }

    function syncModalContent() {
      const raw = document.getElementById('modal-article-content').value;
      document.getElementById('modal-render-container').innerHTML = raw;
      updateWordCount();
    }

    function updateWordCount() {
      const raw = (document.getElementById('modal-article-content') ? document.getElementById('modal-article-content').value : '') || '';
      // Hilangkan tag script, style, dan seluruh tag HTML menggunakan regex agar aman di semua browser
      const clean = raw
        .replace(/<script[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ' ')
        .replace(/<style[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&[a-z]+;/gi, ' ')
        .trim();
      
      const words = clean ? clean.split(/\s+/).filter(w => w.length > 0) : [];
      const wordCount = words.length;
      const readMins = Math.max(1, Math.ceil(wordCount / 200));
      const timeStr = wordCount > 0 ? ` (~${readMins} mnt baca)` : ' (~0 mnt baca)';
      
      const el = document.getElementById('content-word-count');
      if (el) {
        let badgeClass = 'text-amber-700 dark:text-amber-400';
        if (wordCount >= 1000) {
          badgeClass = 'text-emerald-700 dark:text-emerald-400';
        } else if (wordCount >= 500) {
          badgeClass = 'text-brand-600 dark:text-brand-400';
        }
        el.className = `text-xs font-mono font-semibold ${badgeClass}`;
        el.innerText = `${wordCount.toLocaleString('id-ID')} kata${timeStr}` + (wordCount < 600 && wordCount > 0 ? ' (Ideal: 800-1500+)' : '');
      }

      const headerBadge = document.getElementById('modal-word-badge');
      if (headerBadge) {
        let hBadgeClass = 'bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/30';
        if (wordCount >= 1000) {
          hBadgeClass = 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30';
        } else if (wordCount >= 500) {
          hBadgeClass = 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-400 border border-brand-200 dark:border-brand-500/30';
        }
        headerBadge.className = `text-xs font-mono font-semibold px-3 py-1 rounded-full ${hBadgeClass}`;
        headerBadge.innerText = `${wordCount.toLocaleString('id-ID')} kata`;
      }
    }

    function auditArticleSEO(title, meta, content) {
      let score = 0;
      const tLen = (title || '').trim().length;
      const mLen = (meta || '').trim().length;
      const raw = content || '';

      // 1. Title Audit (Max 25 pts)
      const elTitle = document.getElementById('seo-check-title');
      if (tLen >= 50 && tLen <= 60) {
        score += 25;
        if (elTitle) elTitle.className = "px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium";
      } else if (tLen >= 40 && tLen <= 70) {
        score += 15;
        if (elTitle) elTitle.className = "px-2 py-0.5 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium";
      } else {
        score += 5;
        if (elTitle) elTitle.className = "px-2 py-0.5 rounded-lg bg-rose-500/15 text-rose-300 border border-rose-500/30 font-medium";
      }

      // 2. Meta Desc Audit (Max 20 pts)
      const elMeta = document.getElementById('seo-check-meta');
      if (mLen >= 130 && mLen <= 155) {
        score += 20;
        if (elMeta) elMeta.className = "px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium";
      } else if (mLen >= 100 && mLen <= 165) {
        score += 12;
        if (elMeta) elMeta.className = "px-2 py-0.5 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium";
      } else {
        score += 3;
        if (elMeta) elMeta.className = "px-2 py-0.5 rounded-lg bg-rose-500/15 text-rose-300 border border-rose-500/30 font-medium";
      }

      // 3. Word Count Audit (Max 25 pts)
      const clean = raw.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      const words = clean ? clean.split(' ').filter(w => w.length > 0) : [];
      const wCount = words.length;
      const elWords = document.getElementById('seo-check-words');
      if (wCount >= 1000) {
        score += 25;
        if (elWords) elWords.className = "px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium";
      } else if (wCount >= 600) {
        score += 15;
        if (elWords) elWords.className = "px-2 py-0.5 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium";
      } else {
        score += 5;
        if (elWords) elWords.className = "px-2 py-0.5 rounded-lg bg-rose-500/15 text-rose-300 border border-rose-500/30 font-medium";
      }

      // 4. Schema FAQPage Detection (Max 15 pts)
      const hasSchema = raw.includes('application/ld+json') && raw.includes('FAQPage');
      const elSchema = document.getElementById('seo-check-schema');
      if (hasSchema) {
        score += 15;
        if (elSchema) elSchema.className = "px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium";
      } else {
        if (elSchema) elSchema.className = "px-2 py-0.5 rounded-lg bg-slate-800 text-slate-500 border border-slate-700 font-medium";
      }

      // 5. Image & Alt Detection (Max 15 pts)
      const hasImg = raw.includes('<figure') || (raw.includes('<img') && raw.includes('alt='));
      const elImg = document.getElementById('seo-check-img');
      if (hasImg) {
        score += 15;
        if (elImg) elImg.className = "px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium";
      } else {
        if (elImg) elImg.className = "px-2 py-0.5 rounded-lg bg-slate-800 text-slate-500 border border-slate-700 font-medium";
      }

      // Update Gauge
      const badge = document.getElementById('seo-score-badge');
      const status = document.getElementById('seo-score-status');
      const summary = document.getElementById('seo-score-summary');
      if (badge) badge.innerText = score;
      if (status) {
        if (score >= 85) {
          status.innerText = "Sangat Optimal (E-E-A-T)";
          status.className = "text-xs font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/15 px-2.5 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-500/30";
        } else if (score >= 60) {
          status.innerText = "Cukup Baik";
          status.className = "text-xs font-bold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/15 px-2.5 py-0.5 rounded-full border border-amber-200 dark:border-amber-500/30";
        } else {
          status.innerText = "Perlu Optimasi";
          status.className = "text-xs font-bold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/15 px-2.5 py-0.5 rounded-full border border-rose-200 dark:border-rose-500/30";
        }
      }
      if (summary) {
        summary.innerText = `Skor ${score}/100: ${wCount} kata, Judul: ${tLen} char, Meta: ${mLen} char, FAQ Schema: ${hasSchema ? 'Aktif' : 'Tidak'}.`;
      }
    }

    function updateCharCount() {
      const title = document.getElementById('modal-article-title').value;
      const meta = document.getElementById('modal-article-meta').value;
      const content = document.getElementById('modal-article-content').value;
      document.getElementById('title-char-count').innerText = title.length + ' karakter (Ideal: 50-60)';
      document.getElementById('meta-char-count').innerText = meta.length + ' karakter (Ideal: 140-155)';
      auditArticleSEO(title, meta, content);
    }

    async function handleImageUpload(input) {
      if (!input.files || input.files.length === 0) return;
      const file = input.files[0];
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/images/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.success) {
          const finalUrl = data.url.startsWith('http') ? data.url : (window.location.origin + data.url);
          document.getElementById('img-url-input').value = finalUrl;
          if (!document.getElementById('img-alt-input').value) {
            const kw = document.getElementById('modal-article-keyword').value;
            document.getElementById('img-alt-input').value = kw ? ('Ilustrasi panduan ' + kw) : file.name;
          }
          if (data.is_cdn) {
            showToast(`Gambar berhasil dikonversi ke WebP dan diunggah ke Cloud CDN (${data.cdn_provider})! Klik "+ Sisipkan" untuk memasukkannya ke artikel.`, 'success');
          } else {
            showToast('Gambar berhasil dioptimasi ke WebP (Lokal). Catatan: Agar gambar muncul di blog publik, atur CLOUDINARY_URL di file .env.', 'info');
          }
        } else {
          showToast('Gagal upload gambar: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (err) {
        showToast('Error upload: ' + err.message, 'error');
      } finally {
        input.value = '';
      }
    }

    function insertImageSnippet() {
      const url = document.getElementById('img-url-input').value.trim();
      const alt = document.getElementById('img-alt-input').value.trim() || document.getElementById('modal-article-keyword').value.trim() || 'Ilustrasi Artikel';
      const caption = document.getElementById('img-caption-input').value.trim();
      
      if (!url) {
        showToast('Silakan masukkan URL gambar atau unggah file gambar terlebih dahulu.', 'warning');
        return;
      }
      
      const captionHtml = caption ? `<figcaption style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; text-align: center;">${caption}</figcaption>` : '';
      const figureHtml = `
<figure style="text-align: center; margin: 1.75rem 0;">
  <img src="${url}" alt="${alt}" style="border-radius: 12px; max-width: 100%; height: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);" loading="lazy">
  ${captionHtml}
</figure>
`;
      
      const contentArea = document.getElementById('modal-article-content');
      contentArea.value = figureHtml + contentArea.value;
      syncModalContent();
      showToast('Gambar berhasil disisipkan ke dalam draf!', 'success');
    }

    function switchModalView(view) {
      const renderContainer = document.getElementById('modal-render-container');
      const codeContainer = document.getElementById('modal-code-container');
      const btnPreview = document.getElementById('btn-tab-preview');
      const btnCode = document.getElementById('btn-tab-code');
      
      if (view === 'preview') {
        renderContainer.classList.remove('hidden');
        codeContainer.classList.add('hidden');
        btnPreview.className = 'px-3 py-1 text-xs font-semibold rounded bg-brand-600 text-white shadow-sm transition';
        btnCode.className = 'px-3 py-1 text-xs font-semibold rounded text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition';
        syncModalContent();
      } else {
        renderContainer.classList.add('hidden');
        codeContainer.classList.remove('hidden');
        btnCode.className = 'px-3 py-1 text-xs font-semibold rounded bg-brand-600 text-white shadow-sm transition';
        btnPreview.className = 'px-3 py-1 text-xs font-semibold rounded text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition';
      }
    }

    function openNewArticleModal() {
      document.getElementById('modal-article-id').value = '';
      document.getElementById('modal-article-title').value = '';
      document.getElementById('modal-article-keyword').value = '';
      document.getElementById('modal-article-labels').value = 'Tech, Tutorial';
      document.getElementById('modal-article-meta').value = '';
      document.getElementById('modal-article-content').value = '<p>Tulis konten atau masukkan kode HTML draf di sini...</p>';
      const draftBtn = document.getElementById('btn-draft-action');
      if (draftBtn) {
        draftBtn.classList.remove('hidden');
        draftBtn.querySelector('span').innerText = 'Kirim Draft ke Blogger';
      }
      const publishBtn = document.getElementById('btn-publish-action');
      if (publishBtn) {
        publishBtn.classList.remove('hidden');
        publishBtn.querySelector('span').innerText = 'Publish Live ke Blogger';
      }
      const reqReviewBtn = document.getElementById('btn-request-review');
      if (reqReviewBtn) reqReviewBtn.classList.add('hidden');
      const approveBtn = document.getElementById('btn-approve-article');
      if (approveBtn) approveBtn.classList.add('hidden');

      syncModalContent();
      updateCharCount();
      switchModalView('preview');
      updateSerpPreview('Judul Artikel Baru', 'Deskripsi artikel Anda akan tampil di Google Search snippet.');
      document.body.classList.add('overflow-hidden');
      document.getElementById('article-modal').classList.remove('hidden');
    }

    function closeArticleModal() {
      document.getElementById('article-modal').classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    }

    async function updateArticleStatus(articleId, status) {
      try {
        const res = await fetch(`/api/articles/${articleId}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Status artikel berhasil diperbarui', 'success');
          await loadData();
        } else {
          showToast(data.detail || data.error || 'Gagal mengubah status', 'error');
        }
      } catch (e) {
        showToast('Terjadi kesalahan: ' + e.message, 'error');
      }
    }

    async function submitModalForReview() {
      const id = document.getElementById('modal-article-id').value;
      if (!id) {
        showToast('Simpan draf artikel terlebih dahulu.', 'warning');
        return;
      }
      await updateArticleStatus(id, 'pending_review');
      closeArticleModal();
    }

    async function approveModalArticle() {
      const id = document.getElementById('modal-article-id').value;
      if (!id) return;
      await updateArticleStatus(id, 'approved');
      closeArticleModal();
    }


    async function saveArticleDraft() {
      const id = document.getElementById('modal-article-id').value;
      const data = {
        id: id ? parseInt(id) : null,
        title: document.getElementById('modal-article-title').value,
        target_keyword: document.getElementById('modal-article-keyword').value,
        labels: document.getElementById('modal-article-labels').value,
        meta_description: document.getElementById('modal-article-meta').value,
        content_html: document.getElementById('modal-article-content').value,
        blog_id: activeBlog ? activeBlog.id : null
      };
      const res = await fetch('/api/articles/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        closeArticleModal();
        await loadData();
      }
    }

    async function publishArticle(isDraft = false) {
      const id = document.getElementById('modal-article-id').value;
      if (!id) {
        showToast('Simpan draf artikel terlebih dahulu.', 'warning');
        return;
      }
      const title = isDraft ? 'Simpan Draf ke Blogger' : 'Publikasikan Artikel Live';
      const message = isDraft
        ? 'Artikel ini akan diunggah atau diperbarui sebagai DRAFT di Blogger Anda.'
        : 'Artikel ini akan langsung DITERBITKAN secara publik ke Blogger Anda. Lanjutkan?';
      const confirmText = isDraft ? 'Simpan Draf' : 'Publikasikan Sekarang';
      const icon = isDraft ? '📝' : '🚀';

      showConfirm({
        title,
        message,
        confirmText,
        cancelText: 'Batal',
        icon,
        isDestructive: false,
        onConfirm: async () => {
          const btn = isDraft ? document.getElementById('btn-draft-action') : document.getElementById('btn-publish-action');
          const originalHtml = btn ? btn.innerHTML : '';
          if (btn) {
            btn.disabled = true;
            btn.classList.add('opacity-75', 'cursor-not-allowed');
            btn.innerHTML = `
              <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
              <span>Menghubungi Blogger...</span>
            `;
          }
          
          try {
            const res = await fetch(`/api/articles/${id}/publish?is_draft=${isDraft ? 'true' : 'false'}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ is_draft: isDraft })
            });
            const result = await res.json();
            if (result.success) {
              const actionText = result.action === 'updated' ? 'berhasil diperbarui' : 'berhasil dibuat';
              const modeText = isDraft ? 'Draft di Blogger' : 'Live Publik di Blogger';
              if (btn) {
                btn.innerHTML = `
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                  <span>Tersimpan!</span>
                `;
              }
              setTimeout(() => {
                showToast(`Artikel ${actionText} sebagai ${modeText}.`, 'success');
                closeArticleModal();
                loadData();
              }, 250);
            } else {
              showToast('Gagal ke Blogger: ' + (result.error || 'Terjadi kesalahan sistem'), 'error');
              if (btn) {
                btn.disabled = false;
                btn.classList.remove('opacity-75', 'cursor-not-allowed');
                btn.innerHTML = originalHtml;
              }
            }
          } catch (err) {
            showToast('Terjadi kesalahan koneksi: ' + err.message, 'error');
            if (btn) {
              btn.disabled = false;
              btn.classList.remove('opacity-75', 'cursor-not-allowed');
              btn.innerHTML = originalHtml;
            }
          }
        }
      });
    }

    async function quickPublish(id, isDraft = false, btnEl = null) {
      const title = isDraft ? 'Simpan Draf ke Blogger' : 'Publikasi Langsung (Live)';
      const message = isDraft
        ? 'Kirim atau perbarui artikel ini sebagai draf di akun Blogger Anda?'
        : 'Publikasikan artikel ini langsung (live) agar dapat dibaca publik di Blogger?';
      const confirmText = isDraft ? 'Simpan Draf' : 'Publikasikan';
      const icon = isDraft ? '📝' : '🚀';

      showConfirm({
        title,
        message,
        confirmText,
        cancelText: 'Batal',
        icon,
        isDestructive: false,
        onConfirm: async () => {
          let originalHtml = '';
          if (btnEl) {
            originalHtml = btnEl.innerHTML;
            btnEl.disabled = true;
            btnEl.classList.add('opacity-75', 'cursor-not-allowed');
            btnEl.innerHTML = `
              <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
              <span>Syncing...</span>
            `;
          }
          
          try {
            const res = await fetch(`/api/articles/${id}/publish?is_draft=${isDraft ? 'true' : 'false'}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ is_draft: isDraft })
            });
            const result = await res.json();
            if (result.success) {
              if (btnEl) btnEl.innerText = 'Selesai!';
              showToast(`Artikel berhasil ${result.action === 'updated' ? 'diperbarui' : 'disimpan'} di Blogger.`, 'success');
              await loadData();
            } else {
              showToast('Gagal: ' + (result.error || 'Terjadi kesalahan sistem'), 'error');
              if (btnEl) {
                btnEl.disabled = false;
                btnEl.classList.remove('opacity-75', 'cursor-not-allowed');
                btnEl.innerHTML = originalHtml;
              }
            }
          } catch (err) {
            showToast('Terjadi kesalahan koneksi: ' + err.message, 'error');
            if (btnEl) {
              btnEl.disabled = false;

      showToast(`Agent AI sedang meriset topik baru untuk ${bName} di background...`, 'info', 4000);
      
      try {
        const res = await fetch('/api/agent/generate-now', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast('Permintaan diterima! Draf artikel akan otomatis muncul di antrean saat siap.', 'success', 5000);
          const checkInterval = setInterval(async () => {
            await loadData();
          }, 10000);
          
          setTimeout(() => {
            btn.disabled = false;
            btn.classList.remove('opacity-70');
            txt.innerText = 'Buat Draf AI';
            clearInterval(checkInterval);
          }, 120000);
        } else {
          showToast(data.error || 'Gagal memicu agent AI.', 'error', 6000);
          btn.disabled = false;
          btn.classList.remove('opacity-70');
          txt.innerText = 'Buat Draf AI';
        }
      } catch (e) {
        showToast('Terjadi kesalahan: ' + e.message, 'error');
        btn.disabled = false;
        btn.classList.remove('opacity-70');
        txt.innerText = 'Buat Draf AI';
      }
    }

    async function deleteArticle(id, title) {
      showConfirm({
        title: 'Hapus Draf Artikel',
        message: `Hapus artikel "${title || 'ini'}" dari database secara permanen?`,
        confirmText: 'Hapus Artikel',
        isDestructive: true,
        icon: '🗑️',
        onConfirm: async () => {
          try {
            const res = await fetch(`/api/articles/${id}/delete`, { method: 'POST' });
            const result = await res.json();
            if (result.success) {
              showToast('Artikel berhasil dihapus.', 'success');
              const modalId = document.getElementById('modal-article-id').value;
              if (modalId == id) {
                closeArticleModal();
              }
              await loadData();
            } else {
              showToast('Gagal menghapus: ' + (result.error || 'Terjadi kesalahan'), 'error');
            }
          } catch (err) {
            showToast('Error: ' + err.message, 'error');
          }
        }
      });
    }

    async function deleteCurrentArticle() {
      const id = document.getElementById('modal-article-id').value;
      const title = document.getElementById('modal-article-title').value;
      if (!id) {
        closeArticleModal();
        return;
      }
      await deleteArticle(id, title);
    }

