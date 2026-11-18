// --- Blogger Auto-Pilot: SaaS Multi-Tenant Authentication & Session ---
    // --- SaaS Multi-Tenant & Billing Client Suite ---
    let currentUser = null;
    let currentSubscription = null;

    async function loadCurrentUser() {
      try {
        const res = await fetch('/api/saas/auth/me');
        const data = await res.json();
        
        const pillRatio = document.getElementById('plan-credits-ratio');
        const pillName = document.getElementById('plan-name-display');
        const pillBar = document.getElementById('plan-progress-bar');
        const userDisplay = document.getElementById('user-display-email');
        const userAvatar = document.getElementById('user-avatar-initial');
        const dropName = document.getElementById('dropdown-user-name');
        const dropEmail = document.getElementById('dropdown-user-email');
        const menuAuthText = document.getElementById('menu-text-auth-action');

        if (data.authenticated && data.user) {
          currentUser = data.user;
          currentSubscription = data.subscription;

          const name = currentUser.full_name || currentUser.email.split('@')[0];
          userDisplay.innerText = name;
          userAvatar.innerText = name.charAt(0).toUpperCase();
          dropName.innerText = currentUser.full_name || 'Pengguna SaaS';
          dropEmail.innerText = currentUser.email;
          menuAuthText.innerText = 'Keluar (Logout)';

          const tier = (data.subscription?.plan_tier || 'free').toUpperCase();
          const used = data.subscription?.article_credits_used || 0;
          const limit = data.subscription?.article_credits_limit || 3;
          const remaining = Math.max(0, limit - used);
          const pct = Math.min(100, Math.round((used / limit) * 100));

          pillName.innerText = tier;
          pillRatio.innerText = `(${remaining} tersisa)`;
          pillBar.style.width = `${pct}%`;

          const elStatCredits = document.getElementById('stat-credits-remaining');
          const elStatSub = document.getElementById('stat-credits-sub');
          if (elStatCredits) elStatCredits.innerText = `${remaining} Kredit`;
          if (elStatSub) elStatSub.innerText = `${used} terpakai dari ${limit} limit`;
          
          if (pct >= 100) {
            pillBar.className = "bg-rose-500 h-full transition-all duration-300";
          } else {
            pillBar.className = "bg-gradient-to-r from-brand-500 to-indigo-500 h-full transition-all duration-300";
          }
        } else {
          currentUser = null;
          currentSubscription = data.subscription;
          userDisplay.innerText = 'Masuk / Daftar';
          userAvatar.innerText = '?';
          dropName.innerText = 'Tamu (Mode Lokal)';
          dropEmail.innerText = 'Belum terautentikasi';
          menuAuthText.innerText = 'Masuk ke Akun SaaS';
          
          const used = data.subscription?.article_credits_used || 0;
          const limit = data.subscription?.article_credits_limit || 3;
          const remaining = Math.max(0, limit - used);
          pillName.innerText = 'LOKAL';
          pillRatio.innerText = `(${remaining} tersisa)`;
          pillBar.style.width = '30%';

          const elStatCredits = document.getElementById('stat-credits-remaining');
          const elStatSub = document.getElementById('stat-credits-sub');
          if (elStatCredits) elStatCredits.innerText = `${remaining} Kredit`;
          if (elStatSub) elStatSub.innerText = `${used} terpakai dari ${limit} limit`;
        }

        // Show Admin Console button if user has admin privileges
        const adminBtn = document.getElementById('btn-admin-console');
        if (adminBtn) {
          if (data.user && (data.user.role === 'admin' || data.user.email === 'admin@bagustech.id')) {
            adminBtn.classList.remove('hidden');
          } else {
            adminBtn.classList.add('hidden');
          }
        }

        // Sync isolated prompt and knowledge base for current tenant
        try {
          const [pRes, kRes] = await Promise.all([fetch('/api/prompt'), fetch('/api/kb')]);
          const pData = await pRes.json();
          const kData = await kRes.json();
          if (pData && pData.content !== undefined) {
            const pe = document.getElementById('prompt-editor');
            if (pe) pe.value = pData.content;
          }
          if (kData && kData.content !== undefined) {
            const ke = document.getElementById('kb-editor');
            if (ke) ke.value = kData.content;
          }
        } catch (e) {
          console.error('Error syncing prompt/kb:', e);
        }
      } catch (err) {
        console.error('Error loading current user:', err);
      }
    }

    function toggleUserDropdown(forceState) {
      const menu = document.getElementById('user-dropdown-menu');
      if (typeof forceState === 'boolean') {
        if (forceState) menu.classList.remove('hidden');
        else menu.classList.add('hidden');
      } else {
        menu.classList.toggle('hidden');
      }
    }

    // Close user dropdown on outside click
    document.addEventListener('click', function(e) {
      const container = document.getElementById('user-menu-container');
      if (container && !container.contains(e.target)) {
        toggleUserDropdown(false);
      }
    });

    function handleAuthAction() {
      toggleUserDropdown(false);
      if (currentUser) {
        logoutSaas();
      } else {
        openAuthModal('login');
      }
    }

    function openAuthModal(tab = 'login') {
      document.getElementById('auth-modal').classList.remove('hidden');
      document.getElementById('auth-error-alert').classList.add('hidden');
      switchAuthTab(tab);
    }

    function closeAuthModal() {
      document.getElementById('auth-modal').classList.add('hidden');
    }

    function switchAuthTab(tab) {
      const tabLogin = document.getElementById('tab-auth-login');
      const tabReg = document.getElementById('tab-auth-register');
      const formLogin = document.getElementById('form-login');
      const formReg = document.getElementById('form-register');
      const title = document.getElementById('auth-modal-title');
      const alertBox = document.getElementById('auth-error-alert');
      alertBox.classList.add('hidden');

      if (tab === 'login') {
        tabLogin.className = "flex-1 py-3 text-xs font-bold text-brand-600 dark:text-brand-400 border-b-2 border-brand-500 transition";
        tabReg.className = "flex-1 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border-b-2 border-transparent transition";
        formLogin.classList.remove('hidden');
        formReg.classList.add('hidden');
        title.innerText = "Masuk ke Akun SaaS";
      } else {
        tabReg.className = "flex-1 py-3 text-xs font-bold text-emerald-600 dark:text-emerald-400 border-b-2 border-emerald-500 transition";
        tabLogin.className = "flex-1 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border-b-2 border-transparent transition";
        formReg.classList.remove('hidden');
        formLogin.classList.add('hidden');
        title.innerText = "Daftar Akun Baru";
      }
    }

    async function handleLogin(e) {
      e.preventDefault();
      const email = document.getElementById('login-email').value;
      const password = document.getElementById('login-password').value;
      const alertBox = document.getElementById('auth-error-alert');
      const btn = document.getElementById('btn-submit-login');

      btn.disabled = true;
      btn.innerText = "Memverifikasi...";
      alertBox.classList.add('hidden');

      try {
        const res = await fetch('/api/saas/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.error || 'Login gagal.');
        }

        closeAuthModal();
        await loadCurrentUser();
        await loadBlogs();
        await loadData();
        showToast(`Selamat datang kembali, ${data.user.full_name || data.user.email}!`, 'success');
      } catch (err) {
        alertBox.innerText = err.message;
        alertBox.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.innerText = "Masuk ke Dashboard";
      }
    }

    async function handleRegister(e) {
      e.preventDefault();
      const name = document.getElementById('register-name').value;
      const email = document.getElementById('register-email').value;
      const password = document.getElementById('register-password').value;
      const alertBox = document.getElementById('auth-error-alert');
      const btn = document.getElementById('btn-submit-register');

      btn.disabled = true;
      btn.innerText = "Membuat Akun...";
      alertBox.classList.add('hidden');

      try {
        const res = await fetch('/api/saas/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: name })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.error || 'Pendaftaran gagal.');
        }

        closeAuthModal();
        await loadCurrentUser();
        await loadBlogs();
        await loadData();
        showToast('Pendaftaran berhasil! Akun Anda aktif dengan 3 kredit artikel gratis.', 'success');
      } catch (err) {
        alertBox.innerText = err.message;
        alertBox.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.innerText = "Buat Akun & Mulai Gratis";
      }
    }

    function logoutSaas() {
      showConfirm({
        title: 'Keluar dari Akun',
        message: 'Apakah Anda yakin ingin keluar dari akun sesi ini?',
        confirmText: 'Keluar',
        cancelText: 'Tetap Masuk',
        isDestructive: true,
        icon: '🚪',
        onConfirm: async () => {
          try {
            await fetch('/api/saas/auth/logout', { method: 'POST' });
            window.location.reload();
          } catch (err) {
            console.error('Logout error:', err);
            window.location.reload();
          }
        }
      });
    }

