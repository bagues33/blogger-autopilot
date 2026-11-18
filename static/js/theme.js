// --- Blogger Auto-Pilot: Theme, Toasts, and Modal Helpers ---
    // --- Antislop UI/UX Enhancements: Theme Switcher & Toast Suite ---
    function initTheme() {
      try {
        const saved = localStorage.getItem('blogger_theme');
        if (saved === 'light') {
          document.documentElement.classList.remove('dark');
        } else if (saved === 'dark') {
          document.documentElement.classList.add('dark');
        } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
          document.documentElement.classList.remove('dark');
        } else {
          document.documentElement.classList.add('dark');
        }
        updateThemeIcon();
      } catch (e) {
        console.error('Theme init error:', e);
      }
    }

    function toggleTheme() {
      const isDark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('blogger_theme', isDark ? 'dark' : 'light');
      updateThemeIcon();
      showToast(isDark ? 'Mode Gelap diaktifkan' : 'Mode Terang diaktifkan', 'info', 2000);
    }

    function updateThemeIcon() {
      const isDark = document.documentElement.classList.contains('dark');
      const sunIcon = document.getElementById('theme-icon-sun');
      const moonIcon = document.getElementById('theme-icon-moon');
      if (sunIcon && moonIcon) {
        if (isDark) {
          sunIcon.classList.remove('hidden');
          moonIcon.classList.add('hidden');
        } else {
          sunIcon.classList.add('hidden');
          moonIcon.classList.remove('hidden');
        }
      }
    }

    // Floating Non-blocking Toast Notification System
    function showToast(message, type = 'info', duration = 3500) {
      const container = document.getElementById('toast-container');
      if (!container) return;
      
      const cleanMessage = (message || '').replace(/^[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}]\s*/u, '').trim();
      
      const toast = document.createElement('div');
      const typeStyles = {
        success: 'bg-emerald-600 text-white border-emerald-500 shadow-emerald-600/20',
        error: 'bg-rose-600 text-white border-rose-500 shadow-rose-600/20',
        warning: 'bg-amber-600 text-white border-amber-500 shadow-amber-600/20',
        info: 'bg-slate-900 dark:bg-slate-800 text-white border-slate-700 shadow-black/20'
      };
      const iconMap = {
        success: '✓',
        error: '✕',
        warning: '!',
        info: 'ℹ'
      };
      
      const style = typeStyles[type] || typeStyles.info;
      const icon = iconMap[type] || 'ℹ';
      
      toast.className = `pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border shadow-lg text-xs font-medium transition-all duration-300 transform translate-y-2 opacity-0 ${style}`;
      toast.innerHTML = `
        <span class="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center font-bold text-xs shrink-0" aria-hidden="true">${icon}</span>
        <div class="flex-1 min-w-0 pr-1 leading-snug break-words">${cleanMessage}</div>
        <button onclick="this.parentElement.remove()" class="text-white/70 hover:text-white transition font-bold text-sm shrink-0" aria-label="Tutup notifikasi">&times;</button>
      `;
      container.appendChild(toast);
      
      requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
      });
      
      setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }

    // Accessible In-App Confirmation Modal System (Replacing blocking confirm dialogs)
    function showConfirm({
      title = 'Konfirmasi Tindakan',
      message = 'Apakah Anda yakin ingin melanjutkan?',
      confirmText = 'Lanjutkan',
      cancelText = 'Batal',
      isDestructive = false,
      icon = '⚠️',
      onConfirm = () => {}
    }) {
      const modal = document.getElementById('confirm-modal');
      const titleEl = document.getElementById('confirm-modal-title');
      const msgEl = document.getElementById('confirm-modal-msg');
      const btnConfirm = document.getElementById('confirm-modal-btn-action');
      const btnCancel = document.getElementById('confirm-modal-btn-cancel');
      const iconEl = document.getElementById('confirm-modal-icon');
      const iconBg = document.getElementById('confirm-modal-icon-bg');

      if (!modal) {
        if (confirm(message)) onConfirm();
        return;
      }

      titleEl.innerText = title;
      msgEl.innerText = message;
      btnConfirm.innerText = confirmText;
      btnCancel.innerText = cancelText;
      iconEl.innerText = icon;

      if (isDestructive) {
        iconBg.className = "w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mx-auto text-xl font-bold";
        btnConfirm.className = "flex-1 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold transition shadow-sm active:scale-95";
      } else {
        iconBg.className = "w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mx-auto text-xl font-bold";
        btnConfirm.className = "flex-1 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold transition shadow-sm active:scale-95";
      }

      btnConfirm.onclick = () => {
        modal.classList.add('hidden');
        onConfirm();
      };

      btnCancel.onclick = () => {
        modal.classList.add('hidden');
      };

      modal.classList.remove('hidden');
      btnConfirm.focus();
    }

    // Accessible In-App Prompt Modal System (Replacing blocking prompt dialogs)
    function showPrompt({
      title = 'Input Diperlukan',
      message = 'Silakan masukkan data:',
      defaultValue = '',
      placeholder = '',
      inputType = 'text',
      confirmText = 'Simpan',
      cancelText = 'Batal',
      onConfirm = () => {}
    }) {
      const modal = document.getElementById('prompt-modal');
      const titleEl = document.getElementById('prompt-modal-title');
      const msgEl = document.getElementById('prompt-modal-msg');
      const inputEl = document.getElementById('prompt-modal-input');
      const btnConfirm = document.getElementById('prompt-modal-btn-action');
      const btnCancel = document.getElementById('prompt-modal-btn-cancel');

      if (!modal) {
        const val = prompt(message, defaultValue);
        if (val !== null) onConfirm(val);
        return;
      }

      titleEl.innerText = title;
      msgEl.innerText = message;
      inputEl.type = inputType;
      inputEl.value = defaultValue;
      inputEl.placeholder = placeholder;
      btnConfirm.innerText = confirmText;
      btnCancel.innerText = cancelText;

      const cleanup = () => {
        modal.classList.add('hidden');
        btnConfirm.onclick = null;
        btnCancel.onclick = null;
        inputEl.onkeydown = null;
      };

      const handleConfirm = () => {
        const val = inputEl.value;
        cleanup();
        onConfirm(val);
      };

      btnConfirm.onclick = handleConfirm;
      btnCancel.onclick = cleanup;
      inputEl.onkeydown = (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleConfirm();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          cleanup();
        }
      };

      modal.classList.remove('hidden');
      setTimeout(() => {
        inputEl.focus();
        inputEl.select();
      }, 50);
    }

    // Global alert override to route any unexpected error to toast
    window.alert = function(msg) {
      const isErr = /gagal|error|salah|belum|wajib|invalid/i.test(msg);
      const isSucc = /berhasil|sukses|selesai|optimal|selamat/i.test(msg);
      const type = isErr ? 'error' : (isSucc ? 'success' : 'info');
      showToast(msg, type);
    };

    // Google SERP Snippet Preview Updater
    function updateSerpPreview(title, meta) {
      const serpTitle = document.getElementById('serp-preview-title');
      const serpUrl = document.getElementById('serp-preview-url');
      const serpMeta = document.getElementById('serp-preview-meta');
      if (!serpTitle || !serpUrl || !serpMeta) return;

      const t = (title || 'Judul Artikel Anda Akan Tampil di Sini').trim();
      const m = (meta || 'Deskripsi artikel Anda akan tampil di hasil pencarian Google agar menarik minat pembaca.').trim();
      
      serpTitle.innerText = t;
      const blogUrl = activeBlog ? (activeBlog.url || 'https://bagustechnologia.blogspot.com') : 'https://bagustechnologia.blogspot.com';
      serpUrl.innerText = blogUrl.replace(/\/$/, '') + ' › artikel';
      serpMeta.innerText = m;
    }

    // Keyboard Shortcuts (antislop R-32 Accessibility)
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeArticleModal();
        closeAddBlogModal();
        closeAuthModal();
        closeUpgradeModal();
        closeBulkKeywordModal();
        closeAiSuggestModal();
        closeAutopilotModal();
        closeNotificationModal();
        closeAdminModal();
        toggleLandingPreview(false);
      }
    });



// Modal Open & Close Utility Helpers
function openModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
  }
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }
}

    // --- Global Modal Interaction Manager (P1-5) ---
    function closeAllModals() {
      const modalIds = [
        'article-modal', 'add-blog-modal', 'bulk-keyword-modal',
        'niche-suggest-modal', 'auth-modal', 'pricing-modal',
        'notification-modal', 'autopilot-modal', 'admin-modal',
        'admin-tenant-plan-modal', 'admin-tenant-credits-modal',
        'onboarding-wizard-modal', 'image-upload-modal', 'landing-preview-modal'
      ];
      modalIds.forEach(id => {
        const m = document.getElementById(id);
        if (m) m.classList.add('hidden');
      });
      document.body.classList.remove('overflow-hidden');
    }

    // Escape Key Listener
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeAllModals();
        toggleMobileDrawer(false);
      }
    });

    // Backdrop Click Dismissal Setup
    function setupModalBackdrops() {
      const modalIds = [
        'article-modal', 'add-blog-modal', 'bulk-keyword-modal',
        'niche-suggest-modal', 'auth-modal', 'pricing-modal',
        'notification-modal', 'autopilot-modal', 'admin-modal',
        'admin-tenant-plan-modal', 'admin-tenant-credits-modal',
        'onboarding-wizard-modal', 'image-upload-modal'
      ];
      modalIds.forEach(id => {
        const m = document.getElementById(id);
        if (m) {
          m.addEventListener('click', (e) => {
            if (e.target === m) {
              m.classList.add('hidden');
              document.body.classList.remove('overflow-hidden');
            }
          });
        }
      });
    }
