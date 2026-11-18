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



    // --- Phase 2: ROI & Productivity Analytics ---
    function openRoiModal() {
      openModal('roi-modal');
      loadRoiData();
    }

    async function loadRoiData() {
      try {
        const res = await fetch('/api/analytics/roi');
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
          if (hoursSub) hoursSub.innerText = `~${(m.hours_saved / 8).toFixed(1)} hari kerja copywriter`;
          if (costEl) costEl.innerText = m.cost_saved_formatted;
          if (rateEl) rateEl.innerText = `${m.success_rate_percent}%`;
          if (wordsEl) wordsEl.innerText = `${Number(m.total_words).toLocaleString('id-ID')} kata dihasilkan`;
        }
      } catch (err) {
        console.error('Error loading ROI data:', err);
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
