// --- Blogger Auto-Pilot: Main Application Orchestrator & Initialization ---
    // Mobile Drawer (P1-4)
    function toggleMobileDrawer(forceState) {
      const drawer = document.getElementById('mobile-drawer-sheet');
      if (!drawer) return;
      if (typeof forceState === 'boolean') {
        if (forceState) drawer.classList.remove('hidden');
        else drawer.classList.add('hidden');
      } else {
        drawer.classList.toggle('hidden');
      }
    }


    // --- Landing Page Preview Toggle ---
    function toggleLandingPreview(show = true) {
      const modal = document.getElementById('landing-preview-modal');
      if (show) {
        modal.classList.remove('hidden');
      } else {
        modal.classList.add('hidden');
      }
    }



    async function init() {
      initTheme();
      setupModalBackdrops();
      const params = new URLSearchParams(window.location.search);
      if (params.get('landing') === '1') {
        toggleLandingPreview(true);
      }
      if (params.get('auth_success')) {
        const count = params.get('imported') || '0';
        const skipped = parseInt(params.get('skipped_limit') || '0', 10);
        if (skipped > 0) {
          showToast(`Berhasil menghubungkan ${count} blog Google! ${skipped} blog tambahan dilewati karena batas paket Anda. Upgrade paket untuk menghubungkan semua blog.`, 'warning', 7000);
        } else {
          showToast(`Berhasil menghubungkan akun Google! ${count} blog otomatis terdeteksi & terdaftar di dashboard.`, 'success');
        }
        window.history.replaceState({}, document.title, window.location.pathname);
      } else if (params.get('auth_error')) {
        showToast('Gagal otorisasi Google: ' + params.get('auth_error'), 'error');
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      await loadCurrentUser();
      await loadBlogs();
      await loadData();
      loadMidtransScript();
    }
    init();
  
