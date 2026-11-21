// --- Blogger Auto-Pilot: ROI Metrics, Audit Trail, & Onboarding Wizard ---
    // Guided 3-Step Onboarding Stepper Wizard (P1-1)
    let currentWizardStep = 1;

    function dismissOnboardingBanner() {
      const banner = document.getElementById('onboarding-stepper-banner');
      if (banner) banner.classList.add('hidden');
      localStorage.setItem('ob_dismissed', '1');
    }

    function updateOnboardingStepper() {
      const banner = document.getElementById('onboarding-stepper-banner');
      if (!banner) return;
      const isDismissed = localStorage.getItem('ob_dismissed') === '1';
      
      if ((!blogs || blogs.length === 0) && !isDismissed) {
        banner.classList.remove('hidden');
      }

      // Update Step 1: Blogs connection
      const s1Status = document.getElementById('ob-status-1');
      if (s1Status) {
        if (blogs && blogs.length > 0) {
          s1Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30";
          s1Status.innerText = "✓ " + blogs.length + " Terhubung";
        } else {
          s1Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/30";
          s1Status.innerText = "Belum Terhubung";
        }
      }

      // Update Step 2: Keywords
      const s2Status = document.getElementById('ob-status-2');
      if (s2Status) {
        if (keywords && keywords.length > 0) {
          s2Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30";
          s2Status.innerText = "✓ " + keywords.length + " Keyword";
        } else {
          s2Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500";
          s2Status.innerText = "0 Keyword";
        }
      }

      // Update Step 3: Articles
      const s3Status = document.getElementById('ob-status-3');
      if (s3Status) {
        if (articles && articles.length > 0) {
          s3Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30";
          s3Status.innerText = "✓ " + articles.length + " Draf";
        } else {
          s3Status.className = "text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500";
          s3Status.innerText = "Siap Buat";
        }
      }
    }

    function openOnboardingWizard() {
      const banner = document.getElementById('onboarding-stepper-banner');
      if (banner) banner.classList.remove('hidden');
      localStorage.removeItem('ob_dismissed');
      currentWizardStep = 1;
      goToWizardStep(1);
      document.body.classList.add('overflow-hidden');
      document.getElementById('onboarding-wizard-modal').classList.remove('hidden');
    }

    function closeOnboardingWizard() {
      document.getElementById('onboarding-wizard-modal').classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    }

    function goToWizardStep(step) {
      currentWizardStep = step;
      [1, 2, 3].forEach(s => {
        const stepEl = document.getElementById(`wizard-step-${s}`);
        const navEl = document.getElementById(`step-nav-${s}`);
        if (stepEl) {
          if (s === step) stepEl.classList.remove('hidden');
          else stepEl.classList.add('hidden');
        }
        if (navEl) {
          const circle = navEl.querySelector('span:first-child');
          const title = navEl.querySelector('span:last-child');
          if (s === step) {
            if (circle) circle.className = "w-6 h-6 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center shadow-sm";
            if (title) title.className = "text-xs font-bold text-slate-900 dark:text-white";
          } else if (s < step) {
            if (circle) circle.className = "w-6 h-6 rounded-full bg-emerald-600 text-white text-xs font-bold flex items-center justify-center shadow-sm";
            if (title) title.className = "text-xs font-semibold text-emerald-600 dark:text-emerald-400";
          } else {
            if (circle) circle.className = "w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs font-bold flex items-center justify-center";
            if (title) title.className = "text-xs font-semibold text-slate-500 dark:text-slate-400";
          }
        }
      });
    }

    async function wizardGenerateKeywords() {
      const nicheInput = document.getElementById('wizard-niche-input');
      const niche = (nicheInput ? nicheInput.value.trim() : '') || 'Teknologi & Tutorial';
      const btn = document.getElementById('btn-wizard-gen-kw');
      btn.disabled = true;
      btn.innerText = 'Meracik keyword...';
      try {
        const blogParam = activeBlog ? `?blog_id=${activeBlog.id}` : '';
        const res = await fetch('/api/keywords/auto-generate' + blogParam, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast(`Berhasil menambahkan ${data.added_count} keyword awal ke bank ide!`, 'success');
          await loadData();
          goToWizardStep(3);
        } else {
          showToast('Gagal meracik keyword: ' + (data.error || 'Terjadi kesalahan'), 'error');
        }
      } catch (e) {
        showToast('Terjadi kesalahan: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerText = '✨ Racik 5 Keyword Otomatis';
      }
    }



    // --- Phase 2 & Phase 4: ROI, Analytics & Client Export ---
    function openRoiModal() {
      openModal('roi-modal');
      loadRoiData();
    }

    function getSelectedRoiBlogParam() {
      const scopeEl = document.getElementById('roi-blog-scope');
      const scope = scopeEl ? scopeEl.value : 'active';
      if (scope === 'active' && typeof activeBlog !== 'undefined' && activeBlog && activeBlog.id) {
        return activeBlog.id;
      }
      return '';
    }

    async function loadRoiData() {
      try {
        const bId = getSelectedRoiBlogParam();
        const url = bId ? `/api/analytics/roi?blog_id=${encodeURIComponent(bId)}` : '/api/analytics/roi';
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (data.success && data.metrics) {
          const m = data.metrics;
          const totalEl = document.getElementById('roi-total-articles');
          const subEl = document.getElementById('roi-articles-sub');
          const hoursEl = document.getElementById('roi-hours-saved');
          const hoursSub = document.getElementById('roi-hours-sub');
          const costEl = document.getElementById('roi-cost-saved');
          const rateEl = document.getElementById('roi-success-rate');
          const wordsEl = document.getElementById('roi-words-total');

          if (totalEl) totalEl.innerText = m.total_articles;
          if (subEl) subEl.innerText = `${m.published_count} live | ${m.draft_count} draft`;
          if (hoursEl) hoursEl.innerText = `${m.hours_saved} Jam`;
          if (hoursSub) hoursSub.innerText = `~${(m.hours_saved / 8).toFixed(1)} hari kerja`;
          if (costEl) costEl.innerText = m.cost_saved_formatted;
          if (rateEl) rateEl.innerText = `${m.success_rate_percent}%`;
          if (wordsEl) wordsEl.innerText = `${Number(m.total_words).toLocaleString('id-ID')} kata`;

          renderWeeklyChart(m.weekly_production || []);
          renderIntentBars(m.intent_distribution || {}, (m.keywords && m.keywords.total) || 0);
        }
      } catch (err) {
        console.error('Error loading ROI data:', err);
      }
    }

    function renderWeeklyChart(buckets) {
      const container = document.getElementById('roi-weekly-chart');
      if (!container) return;
      if (!buckets.length) {
        container.innerHTML = '<div class="w-full text-center text-xs text-slate-400">Belum ada data produksi</div>';
        return;
      }
      const maxVal = Math.max(1, ...buckets.map(b => b.count));
      container.innerHTML = buckets.map(b => {
        const pct = Math.max(8, Math.round((b.count / maxVal) * 100));
        return `
          <div class="flex-1 flex flex-col items-center justify-end h-full gap-1 group">
            <span class="text-[10px] font-mono font-bold text-slate-600 dark:text-slate-300 opacity-80">${b.count}</span>
            <div class="w-full max-w-[26px] rounded-t-md bg-brand-500/80 dark:bg-brand-500 transition-all duration-300 group-hover:bg-brand-600" style="height: ${pct}%;" title="${b.label}: ${b.count} artikel"></div>
            <span class="text-[10px] text-slate-500 dark:text-slate-400 truncate">${b.label}</span>
          </div>
        `;
      }).join('');
    }

    function renderIntentBars(dist, totalKw) {
      const container = document.getElementById('roi-intent-bars');
      const kwTotalEl = document.getElementById('roi-kw-total');
      if (kwTotalEl) kwTotalEl.innerText = `${totalKw} Keyword`;
      if (!container) return;

      const items = [
        { label: 'Informational', count: dist.Informational || 0, color: 'bg-sky-500' },
        { label: 'Commercial', count: dist.Commercial || 0, color: 'bg-amber-500' },
        { label: 'Transactional', count: dist.Transactional || 0, color: 'bg-emerald-500' }
      ];
      const denom = Math.max(1, totalKw);

      container.innerHTML = items.map(item => {
        const pct = Math.round((item.count / denom) * 100);
        return `
          <div class="space-y-1">
            <div class="flex items-center justify-between text-[11px]">
              <span class="font-semibold text-slate-700 dark:text-slate-300">${item.label}</span>
              <span class="font-mono text-slate-500 dark:text-slate-400">${item.count} (${pct}%)</span>
            </div>
            <div class="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
              <div class="${item.color} h-full rounded-full transition-all duration-300" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    function openPrintableRoiReport() {
      const bId = getSelectedRoiBlogParam();
      const agencyInput = document.getElementById('roi-agency-name');
      const agencyName = agencyInput ? agencyInput.value.trim() : '';

      const params = new URLSearchParams();
      if (bId) params.set('blog_id', bId);
      if (agencyName) params.set('agency_name', agencyName);

      const queryStr = params.toString();
      window.open('/api/analytics/report' + (queryStr ? '?' + queryStr : ''), '_blank');
    }

    async function downloadCsvReport() {
      const bId = getSelectedRoiBlogParam();
      const url = bId ? `/api/analytics/export-csv?blog_id=${encodeURIComponent(bId)}` : '/api/analytics/export-csv';
      try {
        const res = await fetch(url);
        if (res.status === 403) {
          const data = await res.json().catch(() => ({}));
          if (typeof showToast === 'function') showToast(data.detail || 'Fitur ekspor CSV memerlukan paket Pro atau Agency.', 'warning');
          if (typeof openUpgradeModal === 'function') {
            closeModal('roi-modal');
            openUpgradeModal();
          }
          return;
        }
        if (!res.ok) throw new Error('Gagal mengunduh laporan CSV');

        const blob = await res.blob();
        const dlUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = dlUrl;
        a.download = `laporan_konten_${bId || 'semua_blog'}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(dlUrl);
        if (typeof showToast === 'function') showToast('Laporan CSV berhasil diunduh!', 'success');
      } catch (err) {
        if (typeof showToast === 'function') showToast(err.message, 'error');
      }
    }


    // --- Phase 2: Audit Logs ---
    function openAuditModal() {
      openModal('audit-modal');
      loadAuditLogs();
    }

    async function loadAuditLogs() {
      const tbody = document.getElementById('audit-logs-tbody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-slate-500 text-xs">Mengambil catatan audit...</td></tr>';

      try {
        const res = await fetch('/api/audit-logs?limit=30');
        if (!res.ok) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-rose-500 text-xs">Gagal memuat catatan audit.</td></tr>';
          return;
        }
        const data = await res.json();
        if (!data.logs || data.logs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-slate-500 text-xs">Belum ada riwayat aktivitas yang tercatat.</td></tr>';
          return;
        }

        tbody.innerHTML = data.logs.map(l => {
          const dt = l.created_at ? new Date(l.created_at).toLocaleString('id-ID', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : '-';
          return `
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
              <td class="py-2.5 px-4 font-mono text-xs text-slate-500">${dt}</td>
              <td class="py-2.5 px-4 font-semibold text-slate-900 dark:text-white">
                <span class="inline-block px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono">${l.event_type}</span>
              </td>
              <td class="py-2.5 px-4 font-mono text-xs text-slate-600 dark:text-slate-400">${l.entity_id || '-'}</td>
              <td class="py-2.5 px-4 text-slate-500 font-mono text-xs">${l.ip_address || '-'}</td>
            </tr>
          `;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center py-6 text-rose-500 text-xs">Error: ${err.message}</td></tr>`;
      }
    }
