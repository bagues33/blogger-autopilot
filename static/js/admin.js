// --- Blogger Auto-Pilot: Superadmin Command Center ---
    // --- Superadmin Console Logic ---
    let adminTenantsCache = [];

    function openAdminModal() {
      document.getElementById('admin-modal').classList.remove('hidden');
      loadAdminData();
    }

    function closeAdminModal() {
      document.getElementById('admin-modal').classList.add('hidden');
    }

    async function loadAdminData() {
      try {
        const mRes = await fetch('/api/admin/metrics');
        if (mRes.ok) {
          const m = await mRes.json();
          document.getElementById('admin-total-tenants').innerText = m.total_tenants || 0;
          document.getElementById('admin-paying-tenants').innerText = `${m.active_paying || 0} Pelanggan Berbayar`;
          document.getElementById('admin-mrr-display').innerText = 'Rp ' + Number(m.mrr_idr || 0).toLocaleString('id-ID');
          document.getElementById('admin-total-articles').innerText = m.total_articles || 0;
          document.getElementById('admin-articles-breakdown').innerText = `${m.published_articles || 0} Live / ${m.draft_articles || 0} Draf`;
          document.getElementById('admin-total-blogs').innerText = `${m.total_blogs || 0} Blog`;
          document.getElementById('admin-total-keywords').innerText = `${m.total_keywords || 0} Keywords`;
        }

        const tRes = await fetch('/api/admin/tenants');
        if (tRes.ok) {
          const t = await tRes.json();
          adminTenantsCache = t.tenants || [];
          document.getElementById('admin-tenant-count').innerText = adminTenantsCache.length;
          renderAdminTenants(adminTenantsCache);
        }
      } catch (err) {
        console.error('Error loading admin data:', err);
      }
    }

    function renderAdminTenants(tenants) {
      const tbody = document.getElementById('admin-tenants-tbody');
      if (!tbody) return;

      if (!tenants || tenants.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-6 text-slate-500 text-xs">Tidak ada data penyewa yang sesuai filter.</td></tr>';
        return;
      }

      tbody.innerHTML = tenants.map(t => {
        const tierBadge = {
          'free': 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
          'starter': 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-400 border-brand-200 dark:border-brand-500/30',
          'pro': 'bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30',
          'agency': 'bg-purple-50 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-500/30'
        }[t.plan_tier] || 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';

        const statusBadge = t.is_active
          ? '<span class="inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400 font-semibold"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>Aktif</span>'
          : '<span class="inline-flex items-center gap-1 text-xs text-rose-700 dark:text-rose-400 font-semibold"><span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span>Suspend</span>';

        return `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-900/60 transition">
            <td class="py-2.5 px-4">
              <div class="font-bold text-slate-900 dark:text-white text-xs truncate max-w-[180px]">${t.full_name}</div>
              <div class="text-xs text-slate-500 dark:text-slate-400 font-mono truncate max-w-[180px]">${t.email}</div>
            </td>
            <td class="py-2.5 px-3">
              <span class="text-xs font-mono uppercase px-1.5 py-0.5 rounded ${t.role === 'admin' ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 font-bold border border-purple-200 dark:border-purple-700/50' : 'text-slate-500 dark:text-slate-400'}">${t.role}</span>
            </td>
            <td class="py-2.5 px-3">
              <span class="text-xs font-bold uppercase border px-2 py-0.5 rounded-full ${tierBadge}">${t.plan_tier}</span>
            </td>
            <td class="py-2.5 px-3 font-mono text-xs text-slate-700 dark:text-slate-300">
              ${t.credits_used} / ${t.credits_limit}
            </td>
            <td class="py-2.5 px-3 font-mono text-xs text-slate-500 dark:text-slate-400">${t.blogs_count}</td>
            <td class="py-2.5 px-3">${statusBadge}</td>
            <td class="py-2.5 px-4 text-right">
              <div class="flex items-center justify-end gap-1.5">
                <button onclick="adminChangePlan('${t.id}', '${t.email}', '${t.plan_tier}')" class="px-2 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs font-semibold rounded-lg transition" title="Ubah Paket">
                  Paket
                </button>
                <button onclick="adminAddCredits('${t.id}', '${t.email}')" class="px-2 py-1 bg-brand-50 hover:bg-brand-100 dark:bg-brand-500/15 dark:hover:bg-brand-500/25 text-brand-700 dark:text-brand-300 text-xs font-semibold rounded-lg border border-brand-200 dark:border-brand-500/30 transition" title="Tambah Kredit">
                  +Kredit
                </button>
                <button onclick="adminResetPassword('${t.id}', '${t.email}')" class="px-2 py-1 bg-amber-50 hover:bg-amber-100 dark:bg-amber-500/15 dark:hover:bg-amber-500/25 text-amber-700 dark:text-amber-300 text-xs font-semibold rounded-lg border border-amber-200 dark:border-amber-500/30 transition" title="Reset Kata Sandi">
                  Reset Pwd
                </button>
                <button onclick="adminToggleStatus('${t.id}', '${t.email}')" class="px-2 py-1 ${t.is_active ? 'bg-rose-50 hover:bg-rose-100 dark:bg-rose-500/15 dark:hover:bg-rose-500/25 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30' : 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/15 dark:hover:bg-emerald-500/25 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30'} text-xs font-semibold rounded-lg border transition">
                  ${t.is_active ? 'Suspend' : 'Aktifkan'}
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function filterAdminTenants(query) {
      const q = query.toLowerCase().trim();
      if (!q) {
        renderAdminTenants(adminTenantsCache);
        return;
      }
      const filtered = adminTenantsCache.filter(t =>
        t.email.toLowerCase().includes(q) || (t.full_name && t.full_name.toLowerCase().includes(q))
      );
      renderAdminTenants(filtered);
    }

    function adminChangePlan(userId, email, currentTier) {
      showPrompt({
        title: 'Ubah Paket Pengguna',
        message: `Ubah paket langganan untuk ${email} (Pilihan: free, starter, pro, agency):`,
        defaultValue: currentTier,
        placeholder: 'free / starter / pro / agency',
        confirmText: 'Simpan Paket',
        onConfirm: async (newPlan) => {
          if (!newPlan) return;
          const cleanPlan = newPlan.toLowerCase().trim();
          if (!['free', 'starter', 'pro', 'agency'].includes(cleanPlan)) {
            showToast('Paket tidak valid! Pilih: free, starter, pro, atau agency.', 'warning');
            return;
          }

          try {
            const res = await fetch(`/api/admin/tenants/${userId}/plan`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ plan_tier: cleanPlan })
            });
            const data = await res.json();
            if (data.success) {
              showToast(data.message, 'success');
              await loadAdminData();
            } else {
              showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
            }
          } catch (err) {
            showToast('Error: ' + err.message, 'error');
          }
        }
      });
    }

    function adminAddCredits(userId, email) {
      showPrompt({
        title: 'Tambah Bonus Kredit',
        message: `Masukkan jumlah bonus kredit untuk ${email}:`,
        defaultValue: '20',
        placeholder: '20',
        inputType: 'number',
        confirmText: 'Tambah Kredit',
        onConfirm: async (amtStr) => {
          if (!amtStr) return;
          const amount = parseInt(amtStr, 10);
          if (isNaN(amount) || amount <= 0) {
            showToast('Jumlah kredit harus berupa angka positif.', 'warning');
            return;
          }

          try {
            const res = await fetch(`/api/admin/tenants/${userId}/credits`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ amount: amount })
            });
            const data = await res.json();
            if (data.success) {
              showToast(data.message, 'success');
              await loadAdminData();
            } else {
              showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
            }
          } catch (err) {
            showToast('Error: ' + err.message, 'error');
          }
        }
      });
    }

    function adminResetPassword(userId, email) {
      showPrompt({
        title: 'Reset Kata Sandi Pengguna',
        message: `Masukkan kata sandi baru untuk ${email} (minimal 6 karakter):`,
        defaultValue: 'Blogger2026!',
        placeholder: 'Password baru',
        inputType: 'text',
        confirmText: 'Reset Password',
        onConfirm: async (newPw) => {
          if (!newPw || newPw.trim().length < 6) {
            showToast('Kata sandi baru minimal 6 karakter.', 'warning');
            return;
          }

          try {
            const res = await fetch(`/api/admin/tenants/${userId}/reset-password`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ new_password: newPw.trim() })
            });
            const data = await res.json();
            if (data.success) {
              showToast(data.message, 'success');
            } else {
              showToast('Gagal: ' + (data.error || data.detail || 'Terjadi kesalahan sistem'), 'error');
            }
          } catch (err) {
            showToast('Error: ' + err.message, 'error');
          }
        }
      });
    }

    function adminToggleStatus(userId, email) {
      showConfirm({
        title: 'Ubah Status Akun Pengguna',
        message: `Apakah Anda yakin ingin mengubah status aktif/suspend untuk pengguna: ${email}?`,
        confirmText: 'Ubah Status',
        cancelText: 'Batal',
        isDestructive: true,
        icon: '⚠️',
        onConfirm: async () => {
          try {
            const res = await fetch(`/api/admin/tenants/${userId}/toggle-status`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.success) {
              showToast(data.message, 'success');
              await loadAdminData();
            } else {
              showToast('Gagal: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
            }
          } catch (err) {
            showToast('Error: ' + err.message, 'error');
          }
        }
      });
    }

    async function triggerGlobalScheduler() {
      const btn = document.getElementById('btn-admin-run-scheduler');
      if (btn) btn.disabled = true;
      try {
        const res = await fetch('/api/saas/scheduler/run-cycle', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast(`Siklus Scheduler Selesai! Diproses: ${data.processed_count} artikel.`, 'success');
          await loadAdminData();
        } else {
          showToast('Gagal scheduler: ' + (data.error || 'Error scheduler'), 'error');
        }
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    }

