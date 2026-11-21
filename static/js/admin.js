// --- Blogger Auto-Pilot: Superadmin Command Center ---
    let adminTenantsCache = [];
    let adminTierFilter = 'all';
    let adminSearchQuery = '';

    function openAdminModal() {
      document.getElementById('admin-modal').classList.remove('hidden');
      switchAdminTab('tenants');
      loadAdminData();
    }

    function closeAdminModal() {
      document.getElementById('admin-modal').classList.add('hidden');
    }

    function switchAdminTab(tab) {
      const tabs = ['tenants', 'workspaces', 'audit'];
      tabs.forEach(t => {
        const btn = document.getElementById(`admin-tab-btn-${t}`);
        const pane = document.getElementById(`admin-tab-${t}`);
        if (btn) {
          if (t === tab) {
            btn.className = 'px-3.5 py-1.5 rounded-lg font-bold bg-purple-600 text-white shadow-sm transition';
            btn.setAttribute('aria-selected', 'true');
          } else {
            btn.className = 'px-3.5 py-1.5 rounded-lg font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition';
            btn.setAttribute('aria-selected', 'false');
          }
        }
        if (pane) {
          if (t === tab) pane.classList.remove('hidden');
          else pane.classList.add('hidden');
        }
      });

      if (tab === 'workspaces') loadAdminWorkspaces();
      if (tab === 'audit') loadAdminGlobalAudit();
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

          const wsEl = document.getElementById('admin-total-workspaces');
          const wsCountBadge = document.getElementById('admin-ws-count');
          if (wsEl) wsEl.innerText = `${m.total_workspaces || 0} Workspaces (${m.total_team_members || 0} Tim)`;
          if (wsCountBadge) wsCountBadge.innerText = m.total_workspaces || 0;

          const tbEl = document.getElementById('admin-tier-breakdown');
          if (tbEl && m.tier_breakdown) {
            const tb = m.tier_breakdown;
            tbEl.innerText = `F:${tb.free || 0} · S:${tb.starter || 0} · P:${tb.pro || 0} · A:${tb.agency || 0}`;
          }
        }

        const tRes = await fetch('/api/admin/tenants');
        if (tRes.ok) {
          const t = await tRes.json();
          adminTenantsCache = t.tenants || [];
          document.getElementById('admin-tenant-count').innerText = adminTenantsCache.length;
          applyAdminTenantFilters();
        }
      } catch (err) {
        console.error('Error loading admin data:', err);
      }
    }

    function setAdminTierFilter(tier) {
      adminTierFilter = tier;
      const pills = ['all', 'free', 'starter', 'pro', 'agency', 'suspended'];
      pills.forEach(p => {
        const el = document.getElementById(`admin-tier-${p}`);
        if (!el) return;
        if (p === tier) {
          el.className = p === 'suspended'
            ? 'px-2.5 py-1 rounded-lg font-bold bg-rose-600 text-white transition'
            : 'px-2.5 py-1 rounded-lg font-bold bg-purple-600 text-white transition';
        } else {
          el.className = p === 'suspended'
            ? 'px-2.5 py-1 rounded-lg font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition'
            : 'px-2.5 py-1 rounded-lg font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition';
        }
      });
      applyAdminTenantFilters();
    }

    function filterAdminTenants(query) {
      adminSearchQuery = (query || '').toLowerCase().trim();
      applyAdminTenantFilters();
    }

    function applyAdminTenantFilters() {
      let filtered = adminTenantsCache.slice();
      if (adminTierFilter === 'suspended') {
        filtered = filtered.filter(t => !t.is_active);
      } else if (adminTierFilter !== 'all') {
        filtered = filtered.filter(t => (t.plan_tier || 'free').toLowerCase() === adminTierFilter);
      }
      if (adminSearchQuery) {
        filtered = filtered.filter(t =>
          t.email.toLowerCase().includes(adminSearchQuery) ||
          (t.full_name && t.full_name.toLowerCase().includes(adminSearchQuery))
        );
      }
      renderAdminTenants(filtered);
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
                <button onclick="adminToggleRole('${t.id}', '${t.email}', '${t.role}')" class="px-2 py-1 ${t.role === 'admin' ? 'bg-purple-100 hover:bg-purple-200 dark:bg-purple-500/20 dark:hover:bg-purple-500/30 text-purple-800 dark:text-purple-200 border-purple-300 dark:border-purple-500/40' : 'bg-purple-50 hover:bg-purple-100 dark:bg-purple-500/10 dark:hover:bg-purple-500/20 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-500/30'} text-xs font-semibold rounded-lg border transition" title="${t.role === 'admin' ? 'Cabut hak Superadmin' : 'Promosikan jadi Superadmin'}">
                  ${t.role === 'admin' ? 'Cabut Admin' : '👑 Admin'}
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

    async function loadAdminWorkspaces() {
      const tbody = document.getElementById('admin-workspaces-tbody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="5" class="text-center py-6 text-slate-500 text-xs">Memuat data workspaces...</td></tr>';
      try {
        const res = await fetch('/api/admin/workspaces');
        if (!res.ok) throw new Error('Gagal memuat workspaces');
        const data = await res.json();
        const items = data.workspaces || [];
        const badge = document.getElementById('admin-ws-count');
        if (badge) badge.innerText = items.length;

        if (!items.length) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center py-6 text-slate-400 text-xs">Belum ada workspace agensi yang terdaftar.</td></tr>';
          return;
        }
        tbody.innerHTML = items.map(w => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-900/60 transition">
            <td class="py-2.5 px-4 font-bold text-slate-900 dark:text-white">${w.name}</td>
            <td class="py-2.5 px-3">
              <div class="text-xs text-slate-800 dark:text-slate-200 font-semibold">${w.owner_name}</div>
              <div class="text-[11px] text-slate-500 font-mono">${w.owner_email}</div>
            </td>
            <td class="py-2.5 px-3"><span class="text-xs font-bold uppercase px-2 py-0.5 rounded-full bg-purple-50 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">${w.owner_plan}</span></td>
            <td class="py-2.5 px-3 text-center font-mono">${w.member_count}</td>
            <td class="py-2.5 px-3 text-center font-mono">${w.assigned_blogs_count}</td>
          </tr>
        `).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-6 text-rose-500 text-xs">${err.message}</td></tr>`;
      }
    }

    async function loadAdminGlobalAudit() {
      const tbody = document.getElementById('admin-global-audit-tbody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-slate-500 text-xs">Memuat log audit global...</td></tr>';
      try {
        const res = await fetch('/api/admin/audit-logs?limit=50');
        if (!res.ok) throw new Error('Gagal memuat audit log global');
        const data = await res.json();
        const logs = data.logs || [];

        if (!logs.length) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-slate-400 text-xs">Belum ada aktivitas yang tercatat.</td></tr>';
          return;
        }
        tbody.innerHTML = logs.map(l => {
          const ts = l.created_at ? new Date(l.created_at).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-';
          const isAdminEv = (l.event_type || '').startsWith('admin.');
          const evClass = isAdminEv
            ? 'bg-purple-50 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-500/30'
            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
          const metaStr = l.metadata && Object.keys(l.metadata).length ? JSON.stringify(l.metadata).slice(0, 90) : '-';
          return `
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-900/60 transition">
              <td class="py-2 px-4 font-mono text-[11px] text-slate-500 whitespace-nowrap">${ts}</td>
              <td class="py-2 px-3"><span class="px-2 py-0.5 rounded-md border font-mono text-[11px] font-semibold ${evClass}">${l.event_type}</span></td>
              <td class="py-2 px-3 font-mono text-[11px] text-slate-700 dark:text-slate-300">${l.actor_email}</td>
              <td class="py-2 px-4 font-mono text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[260px]" title="${metaStr.replace(/"/g, '&quot;')}">${metaStr}</td>
            </tr>
          `;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center py-6 text-rose-500 text-xs">${err.message}</td></tr>`;
      }
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
              showToast('Gagal: ' + (data.error || data.detail || 'Terjadi kesalahan sistem'), 'error');
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
              showToast('Gagal: ' + (data.error || data.detail || 'Terjadi kesalahan sistem'), 'error');
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

    function adminToggleRole(userId, email, currentRole) {
      const targetRole = currentRole === 'admin' ? 'subscriber' : 'admin';
      const actionLabel = targetRole === 'admin' ? 'mempromosikan menjadi Superadmin' : 'mencabut hak Superadmin';
      showConfirm({
        title: targetRole === 'admin' ? 'Promosikan ke Superadmin' : 'Cabut Hak Superadmin',
        message: `Apakah Anda yakin ingin ${actionLabel} untuk akun: ${email}?`,
        confirmText: targetRole === 'admin' ? 'Jadikan Superadmin' : 'Cabut Hak Admin',
        cancelText: 'Batal',
        isDestructive: targetRole !== 'admin',
        icon: '👑',
        onConfirm: async () => {
          try {
            const res = await fetch(`/api/admin/tenants/${userId}/role`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ role: targetRole })
            });
            const data = await res.json();
            if (data.success) {
              showToast(data.message, 'success');
              await loadAdminData();
            } else {
              showToast('Gagal: ' + (data.detail || data.error || 'Terjadi kesalahan sistem'), 'error');
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
              showToast('Gagal: ' + (data.error || data.detail || 'Terjadi kesalahan sistem'), 'error');
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
          showToast('Gagal scheduler: ' + (data.error || data.detail || 'Error scheduler'), 'error');
        }
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      } finally {
        if (btn) btn.disabled = false;
      }
    }
