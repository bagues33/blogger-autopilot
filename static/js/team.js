/**
 * Blogger Autopilot - Team & Granular Blog RBAC Management (Phase 3)
 * Handles workspace memberships, role assignments (Writer, Editor, Owner),
 * granular blog assignment editing, read-only member views, and dynamic shared credit pool telemetry.
 */

(function () {
  let activeWorkspaceId = null;
  let workspaceMembers = [];
  let availableBlogs = [];
  let isAgencyTier = false;
  let isCurrentUserOwner = false;

  window.openTeamModal = async function () {
    const modal = document.getElementById('team-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    switchTeamTab('members');
    await loadTeamData();
  };

  window.closeTeamModal = function () {
    const modal = document.getElementById('team-modal');
    if (modal) modal.classList.add('hidden');
  };

  window.switchTeamTab = function (tab) {
    const btnMembers = document.getElementById('team-tab-btn-members');
    const btnInvite = document.getElementById('team-tab-btn-invite');
    const tabMembers = document.getElementById('team-tab-members');
    const tabInvite = document.getElementById('team-tab-invite');

    if (tab === 'members') {
      if (btnMembers) {
        btnMembers.className = 'px-3.5 py-1.5 rounded-lg font-bold bg-brand-600 text-white shadow-sm transition';
        btnMembers.setAttribute('aria-selected', 'true');
      }
      if (btnInvite) {
        btnInvite.className = 'px-3.5 py-1.5 rounded-lg font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition';
        btnInvite.setAttribute('aria-selected', 'false');
      }
      if (tabMembers) tabMembers.classList.remove('hidden');
      if (tabInvite) tabInvite.classList.add('hidden');
    } else {
      if (btnInvite) {
        btnInvite.className = 'px-3.5 py-1.5 rounded-lg font-bold bg-brand-600 text-white shadow-sm transition';
        btnInvite.setAttribute('aria-selected', 'true');
      }
      if (btnMembers) {
        btnMembers.className = 'px-3.5 py-1.5 rounded-lg font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition';
        btnMembers.setAttribute('aria-selected', 'false');
      }
      if (tabInvite) tabInvite.classList.remove('hidden');
      if (tabMembers) tabMembers.classList.add('hidden');
      renderInviteBlogCheckboxes();
    }
  };

  async function loadTeamData() {
    const activeView = document.getElementById('team-content-active');
    const lockedView = document.getElementById('team-content-locked');
    const btnInvite = document.getElementById('team-tab-btn-invite');
    const sharedCreditsEl = document.getElementById('team-shared-credits');

    try {
      const wsRes = await fetch('/api/workspaces', { credentials: 'same-origin' });
      if (!wsRes.ok) {
        if (wsRes.status === 403) {
          if (activeView) activeView.classList.add('hidden');
          if (lockedView) lockedView.classList.remove('hidden');
          return;
        }
        throw new Error('Gagal mengambil data workspace');
      }

      const wsData = await wsRes.json();
      const workspaces = wsData.workspaces || [];

      const userRes = await fetch('/api/auth/me', { credentials: 'same-origin' });
      if (userRes.ok) {
        const u = await userRes.json();
        const plan = (u.plan || (u.subscription && u.subscription.plan_tier) || '').toLowerCase();
        isAgencyTier = plan === 'agency' || u.role === 'admin';
      }

      if (!isAgencyTier && workspaces.length === 0) {
        if (activeView) activeView.classList.add('hidden');
        if (lockedView) lockedView.classList.remove('hidden');
        return;
      }

      if (activeView) activeView.classList.remove('hidden');
      if (lockedView) lockedView.classList.add('hidden');

      if (workspaces.length === 0 && isAgencyTier) {
        const createRes = await fetch('/api/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ name: 'Agensi Utama' })
        });
        if (createRes.ok) {
          const cData = await createRes.json();
          activeWorkspaceId = cData.workspace.id;
        }
      } else if (workspaces.length > 0) {
        activeWorkspaceId = workspaces[0].id;
      }

      if (!activeWorkspaceId) return;

      // Fetch members + shared credit pool telemetry
      const memRes = await fetch(`/api/workspaces/${activeWorkspaceId}/members`, { credentials: 'same-origin' });
      if (memRes.ok) {
        const mData = await memRes.json();
        workspaceMembers = mData.members || [];
        isCurrentUserOwner = Boolean(mData.is_current_user_owner);

        // Update dynamic shared credit pool display
        if (sharedCreditsEl) {
          const limit = mData.shared_credits_limit || 600;
          const used = mData.shared_credits_used || 0;
          const remaining = Math.max(0, limit - used);
          sharedCreditsEl.innerText = `${remaining} / ${limit} Kredit`;
        }

        // Toggle invite tab visibility based on ownership
        if (btnInvite) {
          if (isCurrentUserOwner) btnInvite.classList.remove('hidden');
          else btnInvite.classList.add('hidden');
        }
      }

      // Fetch available blogs only if current user is owner/admin
      if (isCurrentUserOwner) {
        try {
          const blogsRes = await fetch(`/api/workspaces/${activeWorkspaceId}/available-blogs`, { credentials: 'same-origin' });
          if (blogsRes.ok) {
            const bData = await blogsRes.json();
            availableBlogs = bData.blogs || [];
          }
        } catch (e) {
          availableBlogs = [];
        }
      } else {
        availableBlogs = [];
      }

      renderMembersList();
    } catch (err) {
      console.error('[TEAM] Error loading team data:', err);
      if (activeView) activeView.classList.add('hidden');
      if (lockedView) lockedView.classList.remove('hidden');
    }
  }

  function renderMembersList() {
    const listEl = document.getElementById('team-members-list');
    const countEl = document.getElementById('team-member-count');
    if (countEl) countEl.innerText = workspaceMembers.length;

    if (!listEl) return;

    if (!workspaceMembers || workspaceMembers.length === 0) {
      listEl.innerHTML = `
        <div class="text-center py-8 text-slate-400 text-xs">Belum ada anggota tim yang diundang.</div>
      `;
      return;
    }

    listEl.innerHTML = workspaceMembers.map(m => {
      let roleBadge = '';
      if (m.role === 'owner') {
        roleBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30">👑 Pemilik Agensi</span>';
      } else if (m.role === 'editor') {
        roleBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">🛡️ Editor (Approver)</span>';
      } else {
        roleBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30">✍️ Writer (Penulis)</span>';
      }

      let blogTags = '';
      if (m.role === 'owner' || m.role === 'admin') {
        blogTags = '<span class="text-xs text-slate-500 dark:text-slate-400 font-medium">Akses ke Semua Blog Klien Agensi</span>';
      } else if (m.assigned_blogs && m.assigned_blogs.length > 0) {
        blogTags = m.assigned_blogs.map(b => `
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            🏷️ ${b.name}
          </span>
        `).join(' ');
      } else {
        blogTags = '<span class="text-xs text-rose-500 dark:text-rose-400 font-medium">Belum ada blog yang ditugaskan</span>';
      }

      const assignedIds = new Set((m.assigned_blogs || []).map(b => b.id));
      const canManageMember = isCurrentUserOwner && !m.is_owner;

      const actionsHtml = canManageMember ? `
        <button onclick="toggleEditMemberBlogs('${m.user_id}')" class="px-2.5 py-1 text-xs text-brand-700 dark:text-brand-300 bg-brand-50 dark:bg-brand-500/10 hover:bg-brand-100 dark:hover:bg-brand-500/20 rounded-lg transition font-medium border border-brand-200 dark:border-brand-500/30 active:scale-95" title="Ubah pembagian akses blog">
          ✏️ Edit Blog
        </button>
        <button onclick="removeTeamMember('${m.user_id}', '${(m.full_name || m.email).replace(/'/g, "\\'")}')" class="px-2.5 py-1 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 rounded-lg transition font-medium border border-rose-200 dark:border-rose-500/20 active:scale-95" title="Cabut akses anggota">
          Cabut Akses
        </button>
      ` : '';

      const editPanelHtml = canManageMember ? `
        <div id="edit-blogs-panel-${m.user_id}" class="hidden w-full mt-3 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2.5">
          <p class="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Pilih Blog yang Diizinkan untuk ${m.full_name || m.email}:</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-36 overflow-y-auto">
            ${availableBlogs.map(b => `
              <label class="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 p-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 cursor-pointer">
                <input type="checkbox" name="edit-blog-${m.user_id}" value="${b.id}" ${assignedIds.has(b.id) ? 'checked' : ''} class="rounded text-brand-600 focus:ring-brand-500">
                <span class="truncate font-medium">${b.name}</span>
              </label>
            `).join('')}
          </div>
          <div class="flex justify-end gap-2">
            <button onclick="toggleEditMemberBlogs('${m.user_id}')" class="px-3 py-1 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">Batal</button>
            <button onclick="saveEditMemberBlogs('${m.user_id}')" class="px-3.5 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-bold transition shadow-sm active:scale-95">Simpan Akses</button>
          </div>
        </div>
      ` : '';

      return `
        <div class="p-4 rounded-xl border border-slate-200 dark:border-slate-800/90 bg-slate-50/50 dark:bg-[#070b14]/50 flex flex-col gap-2 shadow-sm">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center font-bold text-white text-sm shrink-0">
                ${(m.full_name || m.email || 'U')[0].toUpperCase()}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-bold text-sm text-slate-900 dark:text-white">${m.full_name || m.email.split('@')[0]}</span>
                  ${roleBadge}
                </div>
                <p class="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">${m.email}</p>
                <div class="flex items-center gap-1.5 flex-wrap pt-1.5">
                  ${blogTags}
                </div>
              </div>
            </div>
            <div class="shrink-0 flex items-center gap-2">
              ${actionsHtml}
            </div>
          </div>
          ${editPanelHtml}
        </div>
      `;
    }).join('');
  }

  window.toggleEditMemberBlogs = function (userId) {
    const panel = document.getElementById(`edit-blogs-panel-${userId}`);
    if (panel) panel.classList.toggle('hidden');
  };

  window.saveEditMemberBlogs = async function (userId) {
    if (!activeWorkspaceId) return;
    const boxes = document.querySelectorAll(`input[name="edit-blog-${userId}"]:checked`);
    const blogIds = Array.from(boxes).map(c => c.value);

    try {
      const res = await fetch(`/api/workspaces/${activeWorkspaceId}/members/${userId}/blogs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ assigned_blog_ids: blogIds })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Gagal memperbarui akses blog.');
      if (typeof showToast === 'function') showToast('Pembagian akses blog berhasil diperbarui!', 'success');
      await loadTeamData();
    } catch (err) {
      if (typeof showToast === 'function') showToast(err.message, 'error');
    }
  };

  function renderInviteBlogCheckboxes() {
    const cont = document.getElementById('invite-blogs-container');
    if (!cont) return;

    if (!availableBlogs || availableBlogs.length === 0) {
      cont.innerHTML = `
        <p class="text-xs text-slate-400">Tidak ada blog yang tersedia. Hubungkan blog terlebih dahulu.</p>
      `;
      return;
    }

    cont.innerHTML = availableBlogs.map(b => `
      <label class="flex items-center gap-2.5 text-xs text-slate-800 dark:text-slate-200 cursor-pointer p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800/50 transition">
        <input type="checkbox" name="invite-blog-id" value="${b.id}" checked class="rounded border-slate-300 dark:border-slate-700 text-brand-600 focus:ring-brand-500">
        <span class="font-semibold">${b.name}</span>
        <span class="text-slate-400 text-[11px] font-mono">(${b.url || b.id})</span>
      </label>
    `).join('');
  }

  window.toggleAllInviteBlogs = function (btn) {
    const checkboxes = document.querySelectorAll('input[name="invite-blog-id"]');
    if (!checkboxes || checkboxes.length === 0) return;
    const allChecked = Array.from(checkboxes).every(c => c.checked);
    checkboxes.forEach(c => c.checked = !allChecked);
    btn.innerText = allChecked ? 'Pilih Semua' : 'Batal Pilih Semua';
  };

  window.submitTeamInvite = async function () {
    const emailInput = document.getElementById('invite-email');
    const roleInput = document.querySelector('input[name="invite-role"]:checked');
    const submitBtn = document.getElementById('btn-submit-invite');

    if (!emailInput || !emailInput.value.trim()) {
      if (typeof showToast === 'function') showToast('Silakan masukkan alamat email anggota tim.', 'error');
      return;
    }

    const email = emailInput.value.trim().toLowerCase();
    const role = roleInput ? roleInput.value : 'writer';

    const blogCheckboxes = document.querySelectorAll('input[name="invite-blog-id"]:checked');
    const assignedBlogs = Array.from(blogCheckboxes).map(c => c.value);

    if (assignedBlogs.length === 0) {
      if (typeof showToast === 'function') showToast('Pilih minimal satu blog untuk ditugaskan.', 'error');
      return;
    }

    if (!activeWorkspaceId) {
      if (typeof showToast === 'function') showToast('Workspace belum siap.', 'error');
      return;
    }

    try {
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Mengirim Undangan...';
      }

      const res = await fetch(`/api/workspaces/${activeWorkspaceId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          email: email,
          role: role,
          assigned_blog_ids: assignedBlogs
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || 'Gagal mengundang anggota tim.');
      }

      if (typeof showToast === 'function') {
        showToast(`Berhasil menambahkan ${email} sebagai ${role.toUpperCase()}!`, 'success');
      }

      emailInput.value = '';
      switchTeamTab('members');
      await loadTeamData();
    } catch (err) {
      if (typeof showToast === 'function') showToast(err.message, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerText = '🚀 Kirim Undangan & Beri Akses';
      }
    }
  };

  window.removeTeamMember = async function (userId, name) {
    if (!confirm(`Apakah Anda yakin ingin mencabut akses anggota '${name}' dari tim?`)) return;

    try {
      const res = await fetch(`/api/workspaces/${activeWorkspaceId}/members/${userId}`, {
        method: 'DELETE',
        credentials: 'same-origin'
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || data.error || 'Gagal mencabut akses.');
      }

      if (typeof showToast === 'function') showToast('Akses anggota berhasil dicabut.', 'success');
      await loadTeamData();
    } catch (err) {
      if (typeof showToast === 'function') showToast(err.message, 'error');
    }
  };
})();
