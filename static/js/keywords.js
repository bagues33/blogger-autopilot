// --- Blogger Auto-Pilot: Target Keyword Bank & AI Research ---
    function renderKeywords() {
      const list = document.getElementById('keywords-list');
      if (!keywords || !keywords.length) {
        list.innerHTML = `
          <div class="text-center py-8 border border-dashed border-slate-300 dark:border-slate-800 rounded-2xl p-4 space-y-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-500/15 border border-indigo-200 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto font-bold">🎯</div>
            <div>
              <p class="text-slate-800 dark:text-slate-200 font-bold text-xs">Belum ada target keyword</p>
              <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Isi target kata kunci agar Autopilot memiliki topik untuk ditulis.</p>
            </div>
            <div class="flex items-center justify-center gap-2 pt-1 flex-wrap">
              <button onclick="openSuggestModal()" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-500/15 dark:hover:bg-indigo-500/25 border border-indigo-200 dark:border-indigo-500/30 text-indigo-700 dark:text-indigo-400 rounded-lg text-xs font-bold transition flex items-center gap-1 active:scale-95">
                <span>✨ Ide Niche</span>
              </button>
              <button onclick="openBulkKeywordModal()" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-bold transition active:scale-95">
                <span>+ Impor Massal</span>
              </button>
            </div>
          </div>
        `;
        return;
      }
      list.innerHTML = keywords.map(k => `
        <div class="p-3 rounded-xl border border-slate-200 dark:border-slate-800/80 bg-slate-50/80 dark:bg-[#070b14]/50 flex items-center justify-between text-xs gap-2 hover:border-slate-300 dark:hover:border-slate-700 transition">
          <div class="flex-1 min-w-0">
            <span class="font-semibold text-slate-900 dark:text-slate-200 block truncate" title="${k.keyword}">${k.keyword}</span>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-xs text-slate-500 dark:text-slate-400 font-mono">Intent: ${k.search_intent || 'Informational'}</span>
              <span class="text-xs px-1.5 py-0.5 rounded bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium border border-slate-200 dark:border-slate-700/60">${k.priority || 'Medium'}</span>
            </div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="text-xs px-2 py-0.5 rounded-full bg-white dark:bg-slate-800/90 text-slate-700 dark:text-slate-300 font-mono font-medium border border-slate-200 dark:border-slate-700/50">${k.status}</span>
            <button onclick="deleteKeyword(${k.id})" title="Hapus Keyword" class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition text-sm font-bold">&times;</button>
          </div>
        </div>
      `).join('');
    }



    function openNewKeywordModal() {
      openBulkKeywordModal();
    }

    async function deleteKeyword(id) {
      showConfirm({
        title: 'Hapus Target Keyword',
        message: 'Hapus kata kunci ini dari antrean riset konten?',
        confirmText: 'Hapus Keyword',
        isDestructive: true,
        icon: '🗑️',
        onConfirm: async () => {
          const res = await fetch(`/api/keywords/${id}/delete`, { method: 'POST' });
          if (res.ok) {
            showToast('Kata kunci berhasil dihapus.', 'success');
            await loadData();
          } else {
            showToast('Gagal menghapus keyword.', 'error');
          }
        }
      });
    }

    async function autoGenerateKeywords() {
      const btn = document.getElementById('btn-auto-kw');
      if (btn) btn.innerText = 'Menyusun...';
      try {
        const blogParam = activeBlog ? `?blog_id=${activeBlog.id}` : '';
        const res = await fetch('/api/keywords/auto-generate' + blogParam, { method: 'POST' });
        if (res.ok) {
          await loadData();
          const bName = activeBlog ? activeBlog.name : 'Blog';
          showToast(`Berhasil mengisi bank keyword dengan topik SEO berkualitas untuk ${bName}.`, 'success');
        }
      } finally {
        if (btn) btn.innerText = '⚡ Isi Ide SEO';
      }
    }

    function openBulkKeywordModal() {
      document.getElementById('bulk-keyword-modal').classList.remove('hidden');
      document.getElementById('bulk-kw-textarea').focus();
    }

    function closeBulkKeywordModal() {
      document.getElementById('bulk-keyword-modal').classList.add('hidden');
    }

    function updateBulkCount() {
      const text = document.getElementById('bulk-kw-textarea').value || '';
      const lines = text.split('\n').filter(l => l.trim().length > 0);
      document.getElementById('bulk-kw-count-label').innerText = `${lines.length} baris`;
    }

    async function submitBulkKeywords() {
      const text = document.getElementById('bulk-kw-textarea').value;
      const intent = document.getElementById('bulk-kw-intent').value;
      if (!text.trim()) {
        showToast('Silakan masukkan minimal 1 keyword.', 'warning');
        return;
      }
      const btn = document.getElementById('btn-submit-bulk-kw');
      btn.disabled = true;
      btn.innerText = 'Menyimpan...';
      try {
        const res = await fetch('/api/keywords/bulk-add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            keywords_text: text,
            search_intent: intent,
            blog_id: activeBlog ? activeBlog.id : null
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Berhasil menambahkan ${data.added_count} keyword baru ke antrean!`, 'success');
          closeBulkKeywordModal();
          document.getElementById('bulk-kw-textarea').value = '';
          await loadData();
        } else {
          showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Simpan Semua Keyword';
      }
    }

    function openAiSuggestModal() {
      document.getElementById('ai-suggest-modal').classList.remove('hidden');
      document.getElementById('ai-suggest-niche').focus();
    }

    function closeAiSuggestModal() {
      document.getElementById('ai-suggest-modal').classList.add('hidden');
    }

    async function submitAiSuggest() {
      const niche = document.getElementById('ai-suggest-niche').value;
      if (!niche.trim()) {
        showToast('Masukkan topik/niche terlebih dahulu.', 'warning');
        return;
      }
      const btn = document.getElementById('btn-submit-ai-suggest');
      btn.disabled = true;
      btn.innerText = 'Menyusun Ide...';
      try {
        const res = await fetch('/api/keywords/ai-suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            niche_seed: niche,
            blog_id: activeBlog ? activeBlog.id : null
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Berhasil menambahkan ${data.added_count} keyword potensial untuk topik "${niche}".`, 'success');
          closeAiSuggestModal();
          document.getElementById('ai-suggest-niche').value = '';
          await loadData();
        } else {
          showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = '⚡ Hasilkan 8 Keyword';
      }
    }

