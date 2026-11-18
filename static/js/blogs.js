// --- Blogger Auto-Pilot: Blog Management & Blogger API Sync ---

    let blogs = [];

    let activeBlog = null;
    let articles = [];
    let keywords = [];

    async function loadBlogs() {
      try {
        const res = await fetch('/api/blogs');
        blogs = await res.json();
        activeBlog = blogs.find(b => b.is_active === 1) || blogs[0] || null;
        renderBlogSelector();
      } catch (e) {
        console.error('Error loading blogs:', e);
      }
    }

    function renderBlogSelector() {
      const nameEl = document.getElementById('active-blog-display-name');
      const idEl = document.getElementById('active-blog-id');
      const urlEl = document.getElementById('active-blog-url');
      const autopilotEl = document.getElementById('active-blog-autopilot-label');
      const totalBadge = document.getElementById('blog-total-badge');
      const itemsList = document.getElementById('blog-items-list');

      if (!activeBlog || blogs.length === 0) {
        if (nameEl) nameEl.innerText = 'Belum Ada Blog';
        if (idEl) idEl.innerText = '-';
        if (urlEl) {
          urlEl.href = '#';
          urlEl.innerText = 'Hubungkan Blog Baru ↗';
          urlEl.onclick = (e) => { e.preventDefault(); openAddBlogModal(); };
        }
        if (autopilotEl) autopilotEl.innerText = 'Autopilot: Nonaktif';
        if (totalBadge) totalBadge.innerText = '0 Blog';
        if (itemsList) {
          itemsList.innerHTML = `
            <div class="p-3 text-center text-xs text-slate-500 dark:text-slate-400">
              Belum ada blog terhubung.<br>
              <button onclick="openAddBlogModal()" class="mt-2 text-brand-600 dark:text-brand-400 font-bold hover:underline">
                + Hubungkan Akun Google
              </button>
            </div>
          `;
        }
        return;
      }

      if (nameEl) nameEl.innerText = activeBlog.name;
      if (idEl) idEl.innerText = activeBlog.id;
      if (urlEl) {
        urlEl.onclick = null;
        urlEl.href = activeBlog.url || '#';
        urlEl.innerText = (activeBlog.url ? activeBlog.url.replace(/^https?:\/\//, '').replace(/\/$/, '') : activeBlog.name) + ' ↗';
      }
      if (totalBadge) totalBadge.innerText = blogs.length + ' Blog';

      if (itemsList) {
        itemsList.innerHTML = blogs.map(b => {
          const isActive = b.id === activeBlog.id;
          return `
            <div class="flex items-center justify-between p-2 rounded-xl transition ${isActive ? 'bg-brand-50 dark:bg-brand-500/15 border border-brand-200 dark:border-brand-500/30' : 'hover:bg-slate-100 dark:hover:bg-slate-800/80'}">
              <button onclick="selectBlog('${b.id}')" class="flex-1 text-left min-w-0 pr-2">
                <div class="flex items-center gap-1.5">
                  <span class="w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-slate-400'}"></span>
                  <span class="font-bold text-xs text-slate-900 dark:text-white truncate">${b.name}</span>
                  ${isActive ? '<span class="text-xs bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30 px-1.5 py-0.5 rounded font-semibold">Aktif</span>' : ''}
                </div>
                <div class="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5 font-mono">
                  ${b.account_name || 'Akun'} &bull; ID: ${b.id}
                </div>
              </button>
              ${blogs.length > 1 && !isActive ? `
                <button onclick="deleteBlog('${b.id}', '${b.name}')" title="Hapus blog ini" class="w-6 h-6 rounded flex items-center justify-center text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-red-500/10 transition text-xs font-bold shrink-0">&times;</button>
              ` : ''}
            </div>
          `;
        }).join('');
      }
      if (typeof updateOnboardingStepper === 'function') updateOnboardingStepper();
    }

    function toggleBlogDropdown() {
      const menu = document.getElementById('blog-dropdown-menu');
      if (menu) menu.classList.toggle('hidden');
    }

    document.addEventListener('click', (e) => {
      const container = document.getElementById('blog-dropdown-container');
      const menu = document.getElementById('blog-dropdown-menu');
      if (container && menu && !container.contains(e.target)) {
        menu.classList.add('hidden');
      }
    });

    async function selectBlog(id) {
      try {
        const res = await fetch('/api/blogs/select', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ blog_id: id })
        });
        if (res.ok) {
          activeBlog = blogs.find(b => b.id === id);
          blogs.forEach(b => b.is_active = (b.id === id ? 1 : 0));
          renderBlogSelector();
          const menu = document.getElementById('blog-dropdown-menu');
          if (menu) menu.classList.add('hidden');
          await loadData();
        }
      } catch (e) {
        showToast('Gagal berganti blog: ' + e.message, 'error');
      }
    }

    function openAddBlogModal() {
      const menu = document.getElementById('blog-dropdown-menu');
      if (menu) menu.classList.add('hidden');
      document.getElementById('new-blog-id').value = '';
      document.getElementById('new-blog-name').value = '';
      document.getElementById('new-blog-url').value = '';
      document.getElementById('new-blog-account').value = '';
      document.getElementById('new-blog-niche').value = '';
      document.getElementById('token-upload-status').innerText = '';
      toggleTokenUpload(false);
      document.getElementById('add-blog-modal').classList.remove('hidden');
    }

    function closeAddBlogModal() {
      document.getElementById('add-blog-modal').classList.add('hidden');
    }

    function toggleTokenUpload(show) {
      const area = document.getElementById('token-upload-area');
      if (area) {
        if (show) area.classList.remove('hidden');
        else area.classList.add('hidden');
      }
    }

    let generatedTokenPath = null;

    async function openOAuthLoginPopup() {
      try {
        const res = await fetch('/api/auth/url');
        const data = await res.json();
        if (data.success && data.auth_url) {
          window.open(data.auth_url, '_blank');
          document.getElementById('oauth-code-input-group').classList.remove('hidden');
        } else {
          showToast('Gagal mendapatkan Auth URL: ' + (data.error || 'Pastikan file client_secret.json sudah diletakkan di direktori proyek.'), 'error');
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      }
    }

    async function submitOAuthCode() {
      const codeVal = document.getElementById('oauth-code-input').value.trim();
      if (!codeVal) {
        showToast('Silakan tempel URL redirect atau kode otorisasi dari Google terlebih dahulu.', 'warning');
        return;
      }
      const statusEl = document.getElementById('token-upload-status');
      statusEl.className = 'text-xs text-amber-400 font-semibold';
      statusEl.innerText = '⏳ Memverifikasi kode dengan Google...';
      try {
        const tokenName = 'token_' + Math.random().toString(36).substring(2, 10) + '.json';
        const res = await fetch('/api/auth/exchange', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: codeVal, token_filename: tokenName })
        });
        const data = await res.json();
        if (data.success) {
          generatedTokenPath = data.token_file;
          statusEl.className = 'text-xs text-emerald-700 dark:text-emerald-400 font-semibold';
          statusEl.innerText = '✓ Token berhasil dibuat dan terverifikasi!';
          document.getElementById('oauth-code-input-group').classList.add('hidden');
        } else {
          statusEl.className = 'text-xs text-rose-700 dark:text-rose-400 font-semibold';
          statusEl.innerText = '✗ Gagal: ' + (data.error || 'Kode tidak valid');
        }
      } catch (e) {
        statusEl.className = 'text-xs text-rose-700 dark:text-rose-400 font-semibold';
        statusEl.innerText = 'Error: ' + e.message;
      }
    }

    async function saveNewBlog() {
      const id = document.getElementById('new-blog-id').value.trim();
      const name = document.getElementById('new-blog-name').value.trim();
      const url = document.getElementById('new-blog-url').value.trim();
      const account = document.getElementById('new-blog-account').value.trim();
      const niche = document.getElementById('new-blog-niche').value.trim();
      const tokenChoice = document.querySelector('input[name="token-choice"]:checked').value;

      if (!id || !name) {
        showToast('ID Blog dan Nama Blog wajib diisi.', 'warning');
        return;
      }

      const btn = document.getElementById('btn-save-new-blog');
      btn.disabled = true;
      btn.innerText = 'Menyimpan...';

      let tokenFile = null;
      if (tokenChoice === 'new') {
        if (generatedTokenPath) {
          tokenFile = generatedTokenPath;
        } else {
          const fileInput = document.getElementById('new-blog-token-file');
          if (!fileInput.files || fileInput.files.length === 0) {
            showToast('Silakan login Google via tombol di atas atau pilih file token.json terlebih dahulu.', 'warning');
            btn.disabled = false;
            btn.innerText = 'Simpan & Daftarkan';
            return;
          }
          const formData = new FormData();
          formData.append('file', fileInput.files[0]);
          try {
            const upRes = await fetch('/api/blogs/upload-token', {
              method: 'POST',
              body: formData
            });
            const upData = await upRes.json();
            if (!upData.success) {
              throw new Error(upData.error || 'Gagal upload token');
            }
            tokenFile = upData.token_file;
          } catch (e) {
            showToast('Gagal mengunggah token: ' + e.message, 'error');
            btn.disabled = false;
            btn.innerText = 'Simpan & Daftarkan';
            return;
          }
        }
      } else {
        tokenFile = activeBlog ? activeBlog.token_file : 'token.json';
      }

      try {
        const res = await fetch('/api/blogs/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            id: id,
            name: name,
            url: url,
            account_name: account || 'Akun Google',
            token_file: tokenFile,
            niche_description: niche
          })
        });
        const data = await res.json();
        if (data.success) {
          closeAddBlogModal();
          await loadBlogs();
          await selectBlog(id);
          showToast('Blog baru berhasil didaftarkan dan diaktifkan!', 'success');
        } else {
          showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (e) {
        showToast('Terjadi kesalahan: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Simpan & Daftarkan';
      }
    }

    async function deleteBlog(id, name) {
      showConfirm({
        title: 'Hapus Blog Terhubung',
        message: `Hapus blog "${name}" (ID: ${id}) dari daftar dashboard?`,
        confirmText: 'Hapus Blog',
        isDestructive: true,
        icon: '🗑️',
        onConfirm: async () => {
          try {
            const res = await fetch(`/api/blogs/${id}/delete`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
              showToast('Blog berhasil dihapus dari daftar.', 'success');
              await loadBlogs();
              if (activeBlog) await loadData();
            } else {
              showToast(data.error || 'Gagal menghapus blog.', 'error');
            }
          } catch (e) {
            showToast('Terjadi kesalahan: ' + e.message, 'error');
          }
        }
      });
    }


    // --- Two-Way Blogger Synchronization ---
    async function syncBloggerPosts() {
      if (!activeBlog) {
        showToast('Pilih blog terlebih dahulu untuk disinkronkan.', 'warning');
        return;
      }
      const btn = document.getElementById('btn-sync-blogger');
      const icon = document.getElementById('sync-icon');
      const txt = document.getElementById('sync-btn-text');
      if (icon) icon.classList.add('animate-spin');
      if (txt) txt.innerText = 'Menyinkronkan...';
      if (btn) btn.disabled = true;

      try {
        const res = await fetch(`/api/blogs/${activeBlog.id}/sync-blogger-posts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          await loadData();
        } else {
          showToast('Gagal sinkronisasi: ' + (data.error || 'Terjadi kesalahan'), 'error');
        }
      } catch (err) {
        showToast('Error sinkronisasi: ' + err.message, 'error');
      } finally {
        if (icon) icon.classList.remove('animate-spin');
        if (txt) txt.innerText = 'Sinkron Blogger';
        if (btn) btn.disabled = false;
      }
    }

