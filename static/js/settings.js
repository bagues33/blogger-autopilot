// --- Blogger Auto-Pilot: Settings (KB, Autopilot, Notifications, BYOK) ---

    function switchRightTab(tab) {
      const kbContent = document.getElementById('tab-kb-content');
      const promptContent = document.getElementById('tab-prompt-content');
      const kbActions = document.getElementById('kb-actions');
      const promptActions = document.getElementById('prompt-actions');
      const tabKbBtn = document.getElementById('tab-kb-btn');
      const tabPromptBtn = document.getElementById('tab-prompt-btn');
      
      if (tab === 'kb') {
        kbContent.classList.remove('hidden');
        promptContent.classList.add('hidden');
        kbActions.classList.remove('hidden');
        promptActions.classList.add('hidden');
        tabKbBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-600 text-white shadow-sm transition';
        tabPromptBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition';
      } else {
        kbContent.classList.add('hidden');
        promptContent.classList.remove('hidden');
        kbActions.classList.add('hidden');
        promptActions.classList.remove('hidden');
        tabPromptBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-600 text-white shadow-sm transition';
        tabKbBtn.className = 'px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition';
      }
    }

    async function savePrompt() {
      const content = document.getElementById('prompt-editor').value;
      const btn = document.getElementById('btn-save-prompt');
      btn.innerText = 'Menyimpan...';
      const res = await fetch('/api/prompt/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
      });
      if (res.ok) {
        btn.innerText = 'Tersimpan ✓';
        setTimeout(() => { btn.innerText = 'Simpan Prompt'; }, 2000);
      }
    }

    async function saveKb() {
      const content = document.getElementById('kb-editor').value;
      const btn = document.getElementById('btn-save-kb');
      btn.innerText = 'Menyimpan...';
      try {
        const res = await fetch('/api/kb/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          btn.innerText = 'Tersimpan ✓';
          setTimeout(() => { btn.innerText = 'Simpan'; }, 2000);
          showToast('Knowledge Base kustom berhasil disimpan.', 'success');
        } else {
          btn.innerText = 'Simpan';
          showToast('Gagal: ' + (data.detail || data.error || 'Terjadi kesalahan'), 'error');
          if (res.status === 403 && typeof openUpgradeModal === 'function') {
            setTimeout(openUpgradeModal, 800);
          }
        }
      } catch (err) {
        btn.innerText = 'Simpan';
        showToast('Error koneksi: ' + err.message, 'error');
      }
    }

    async function uploadPdf(input) {
      if (!input.files || input.files.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < input.files.length; i++) {
        formData.append('files', input.files[i]);
      }
      
      const count = input.files.length;
      const btn = document.getElementById('btn-save-kb');
      btn.innerText = 'Memproses ' + count + ' PDF...';
      try {
        const res = await fetch('/api/kb/upload-pdf', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.success) {
          document.getElementById('kb-editor').value = data.content;
          showToast('Berhasil mengekstrak ' + data.total_files + ' file PDF (' + data.total_pages + ' total halaman). Materi sudah ditambahkan ke Knowledge Base.', 'success');
        } else {
          showToast('Gagal memproses PDF: ' + (data.detail || data.error || 'Terjadi kesalahan'), 'error');
          if (res.status === 403 && typeof openUpgradeModal === 'function') {
            setTimeout(openUpgradeModal, 800);
          }
        }
      } catch (err) {
        showToast('Terjadi kesalahan saat upload PDF: ' + err.message, 'error');
      } finally {
        btn.innerText = 'Simpan';
        input.value = '';
      }
    }

    async function openAutopilotModal() {
      if (!activeBlog) {
        showToast('Pilih blog terlebih dahulu.', 'warning');
        return;
      }
      document.getElementById('autopilot-modal').classList.remove('hidden');
      document.getElementById('autopilot-modal-subtitle').innerText = `Blog Aktif: ${activeBlog.name} (${activeBlog.id})`;
      try {
        const res = await fetch(`/api/blogs/${activeBlog.id}/autopilot-settings`);
        const data = await res.json();
        document.getElementById('autopilot-enabled-toggle').checked = Boolean(data.autopilot_enabled);
        document.getElementById('autopilot-publish-mode').value = data.publish_mode || 'blogger_draft';
        document.getElementById('autopilot-schedule-freq').value = data.schedule || 'daily';
      } catch (e) {
        console.error('Error fetching autopilot settings:', e);
      }
    }

    function closeAutopilotModal() {
      document.getElementById('autopilot-modal').classList.add('hidden');
    }

    async function saveAutopilotSettings() {
      if (!activeBlog) return;
      const enabled = document.getElementById('autopilot-enabled-toggle').checked;
      const mode = document.getElementById('autopilot-publish-mode').value;
      const schedule = document.getElementById('autopilot-schedule-freq').value;

      const btn = document.getElementById('btn-save-autopilot');
      btn.disabled = true;
      btn.innerText = 'Menyimpan...';
      try {
        const res = await fetch('/api/blogs/autopilot-settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            blog_id: activeBlog.id,
            autopilot_enabled: enabled,
            publish_mode: mode,
            schedule: schedule
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          closeAutopilotModal();
          const label = document.getElementById('active-blog-autopilot-label');
          if (label) label.innerText = enabled ? 'Autopilot: Aktif' : 'Autopilot: Nonaktif';
        } else {
          showToast('Gagal: ' + (data.detail || data.error || 'Terjadi kesalahan sistem'), 'error');
          if (res.status === 403 && typeof openUpgradeModal === 'function') {
            closeAutopilotModal();
            setTimeout(openUpgradeModal, 600);
          }
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Simpan Pengaturan';
      }
    }

    // --- Notification Settings Modal Logic ---
    function openNotificationModal() {
      document.getElementById('notification-modal').classList.remove('hidden');
      loadNotificationSettings();
    }

    function closeNotificationModal() {
      document.getElementById('notification-modal').classList.add('hidden');
    }

    async function loadNotificationSettings() {
      try {
        const res = await fetch('/api/notifications/settings');
        const data = await res.json();
        document.getElementById('notify-tg-token').value = data.telegram_bot_token || '';
        document.getElementById('notify-tg-chat-id').value = data.telegram_chat_id || '';
        document.getElementById('notify-webhook-url').value = data.webhook_url || '';
        document.getElementById('notify-toggle-draft').checked = data.notify_on_draft !== false;
        document.getElementById('notify-toggle-publish').checked = data.notify_on_publish !== false;
        document.getElementById('notify-toggle-credit').checked = data.notify_on_credit_low !== false;
      } catch (e) {
        console.error('Error loading notification settings:', e);
      }
    }

    async function saveNotificationSettings() {
      const btn = document.getElementById('btn-save-notifications');
      btn.innerText = 'Menyimpan...';
      btn.disabled = true;

      const payload = {
        telegram_bot_token: document.getElementById('notify-tg-token').value.trim(),
        telegram_chat_id: document.getElementById('notify-tg-chat-id').value.trim(),
        webhook_url: document.getElementById('notify-webhook-url').value.trim(),
        notify_on_draft: document.getElementById('notify-toggle-draft').checked,
        notify_on_publish: document.getElementById('notify-toggle-publish').checked,
        notify_on_credit_low: document.getElementById('notify-toggle-credit').checked
      };

      try {
        const res = await fetch('/api/notifications/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          closeNotificationModal();
        } else {
          showToast('Gagal menyimpan: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      } finally {
        btn.innerText = 'Simpan Pengaturan';
        btn.disabled = false;
      }
    }

    async function testNotificationChannel() {
      const token = document.getElementById('notify-tg-token').value.trim();
      const chatId = document.getElementById('notify-tg-chat-id').value.trim();
      const webhook = document.getElementById('notify-webhook-url').value.trim();

      if (!token && !webhook) {
        showToast('Harap isi Telegram Bot Token & Chat ID atau Webhook URL terlebih dahulu sebelum menguji.', 'warning');
        return;
      }

      const btn = document.getElementById('btn-test-notification');
      btn.innerText = 'Menguji...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/notifications/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            telegram_bot_token: token,
            telegram_chat_id: chatId,
            webhook_url: webhook
          })
        });
        const data = await res.json();
        if (data.success) {
          const isTgOk = data.results?.telegram?.success;
          const isWhOk = data.results?.webhook?.success;
          const statusText = (isTgOk || isWhOk)
            ? 'Uji coba notifikasi berhasil dikirim!'
            : 'Uji coba selesai diperiksa.';
          showToast(statusText, isTgOk || isWhOk ? 'success' : 'info');
        } else {
          showToast('Pengujian gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      } finally {
        btn.innerText = '🚀 Kirim Pesan Uji Coba';
        btn.disabled = false;
      }
    }


    // --- Phase 2: BYOK (Bring-Your-Own-Key) ---
    function openByokModal() {
      openModal('byok-modal');
      loadByokSettings();
    }

    async function loadByokSettings() {
      try {
        const res = await fetch('/api/settings/byok');
        if (!res.ok) return;
        const d = await res.json();
        const gMask = document.getElementById('byok-gemini-masked');
        const oMask = document.getElementById('byok-openai-masked');
        const rMask = document.getElementById('byok-groq-masked');
        const banner = document.getElementById('byok-status-banner');

        if (gMask) gMask.innerText = d.has_gemini ? `Aktif: ${d.masked_gemini}` : 'Belum diatur';
        if (oMask) oMask.innerText = d.has_openai ? `Aktif: ${d.masked_openai}` : 'Belum diatur';
        if (rMask) rMask.innerText = d.has_groq ? `Aktif: ${d.masked_groq}` : 'Belum diatur';

        if (banner) {
          if (d.byok_active) {
            banner.className = 'p-3 rounded-xl text-xs font-semibold bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30';
            banner.innerHTML = '✅ Mode BYOK Aktif: Sistem menggunakan kuota token API pribadi Anda.';
            banner.classList.remove('hidden');
          } else {
            banner.classList.add('hidden');
          }
        }
      } catch (err) {
        console.error('Error loading BYOK:', err);
      }
    }

    async function saveByokSettings() {
      const g = document.getElementById('byok-gemini-key').value;
      const o = document.getElementById('byok-openai-key').value;
      const r = document.getElementById('byok-groq-key').value;

      const payload = {};
      if (g) payload.custom_gemini_key = g;
      if (o) payload.custom_openai_key = o;
      if (r) payload.custom_groq_key = r;

      try {
        const res = await fetch('/api/settings/byok', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Kunci API BYOK berhasil disimpan.', 'success');
          document.getElementById('byok-gemini-key').value = '';
          document.getElementById('byok-openai-key').value = '';
          document.getElementById('byok-groq-key').value = '';
          loadByokSettings();
        } else {
          showToast('Gagal menyimpan: ' + (data.detail || data.error || 'Terjadi kesalahan'), 'error');
          if (res.status === 403 && typeof openUpgradeModal === 'function') {
            setTimeout(openUpgradeModal, 600);
          }
        }
      } catch (err) {
        showToast('Error koneksi: ' + err.message, 'error');
      }
    }

