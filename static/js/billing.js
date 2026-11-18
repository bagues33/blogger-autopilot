// --- Blogger Auto-Pilot: Pricing & Midtrans Payment Gateway ---
    function openUpgradeModal() {
      document.getElementById('upgrade-modal').classList.remove('hidden');
      loadMidtransScript();
    }

    function closeUpgradeModal() {
      document.getElementById('upgrade-modal').classList.add('hidden');
    }

    async function loadMidtransScript() {
      try {
        const res = await fetch('/api/billing/plans');
        const data = await res.json();
        if (data.snap_js_url && !document.getElementById('midtrans-snap-script')) {
          const script = document.createElement('script');
          script.id = 'midtrans-snap-script';
          script.src = data.snap_js_url;
          script.setAttribute('data-client-key', data.midtrans_client_key || '');
          document.head.appendChild(script);
        }
      } catch (e) {
        console.log('Notice: Midtrans script load deferred', e);
      }
    }

    async function payWithMidtrans(planTier) {
      if (!currentUser) {
        showToast('Silakan masuk atau buat akun terlebih dahulu sebelum melakukan pembayaran.', 'warning');
        closeUpgradeModal();
        openAuthModal('register');
        return;
      }

      try {
        const res = await fetch('/api/billing/create-snap-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plan_tier: planTier })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.error || 'Gagal memulai transaksi Midtrans.');
        }

        if (window.snap && data.token && !data.is_mock) {
          window.snap.pay(data.token, {
            onSuccess: async function(result) {
              showToast('Pembayaran berhasil dikonfirmasi! Kuota paket langganan Anda telah diperbarui.', 'success');
              closeUpgradeModal();
              await loadCurrentUser();
            },
            onPending: function(result) {
              showToast('Menunggu pembayaran. Silakan transfer melalui Nomor VA / QRIS yang tertera di layar.', 'info');
            },
            onError: function(result) {
              showToast('Pembayaran dibatalkan atau terjadi kesalahan.', 'error');
            },
            onClose: function() {
              console.log('Customer closed popup');
            }
          });
        } else {
          // If demo mock key is used or direct simulation
          showConfirm({
            title: `Simulasi Pembayaran (${data.plan_name})`,
            message: `Order ID: ${data.order_id} | Jumlah: Rp ${Number(data.amount).toLocaleString('id-ID')}. Konfirmasi aktivasi paket langganan ini?`,
            confirmText: 'Aktivasi Paket',
            cancelText: 'Batal',
            icon: '💳',
            isDestructive: false,
            onConfirm: async () => {
              await simulateDemoPayment(planTier);
            }
          });
        }
      } catch (err) {
        showToast('Error Midtrans: ' + err.message, 'error');
      }
    }

    async function simulateDemoPayment(planTier) {
      try {
        const res = await fetch('/api/billing/upgrade-demo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plan_tier: planTier })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          closeUpgradeModal();
          await loadCurrentUser();
        } else {
          showToast('Gagal aktivasi demo: ' + (data.error || 'Terjadi kesalahan sistem'), 'error');
        }
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      }
    }

