# Handoff Report — Explorer 2: User Journeys & Onboarding Audit

**Auditor Role**: Explorer 2: User Journeys & Onboarding Auditor  
**Date**: 2026-11-07  
**Working Directory**: `/Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding/`  
**Target Application**: Blogger Auto-Pilot SaaS (`app.py`, `templates/index.html`, `routers/*`, `content_generator.py`, `autopilot_scheduler.py`)

---

## 1. Observations

### 1.1 Journey 1: Initial Arrival & Landing Page Value Proposition
- **Observation 1.1.1 (Root Endpoint Bypasses Landing Page)**: In `app.py` lines 85–103, `GET /` directly reads and serves `templates/index.html` with injected `{{ kb_content }}` and `{{ prompt_content }}`. There is no route separation between public marketing landing and internal tenant application.
- **Observation 1.1.2 (Hidden Landing Page Modal)**: In `templates/index.html` lines 1201–1203:
  ```html
  <!-- SaaS Public Marketing Landing Page Modal -->
  <div id="landing-preview-modal" class="fixed inset-0 bg-white/95 dark:bg-[#070b14]/98 backdrop-blur-xl z-50 hidden overflow-y-auto text-slate-900 dark:text-white">
  ```
  The entire marketing landing page (Hero, value propositions, pricing tables, CTA buttons) is embedded as a hidden modal (`class="... hidden"`).
- **Observation 1.1.3 (Landing Modal Launch Condition)**: In `templates/index.html` lines 3658–3661:
  ```javascript
  const params = new URLSearchParams(window.location.search);
  if (params.get('landing') === '1') {
    toggleLandingPreview(true);
  }
  ```
  The landing page is only displayed if a visitor appends `?landing=1` to the URL or navigates to it from the user dropdown menu (`templates/index.html` line 310). A standard visitor arriving at `https://domain.com/` is immediately dropped into the authenticated Studio dashboard.
- **Observation 1.1.4 (Default Admin Fallback for Anonymous Visitors)**: In `dependencies.py` lines 40–53 and `routers/auth.py` lines 130–136:
  ```python
  @router.get('/api/saas/auth/me')
  def api_saas_me(request: Request, db: Session = Depends(get_saas_db)):
      user = get_session_user(request, db)
      if not user:
          user = get_or_create_default_admin(db)
          is_default = True
      else:
          is_default = False
  ```
  Unauthenticated visitors automatically inherit the default admin tenant (`admin@bagustech.id`). In `templates/index.html` lines 2960–2979, the client labels this state as `"Tamu (Mode Lokal)"` and renders default admin data (metrics, blog ID, draft articles, and keywords).

---

### 1.2 Journey 2: User Authentication, Signup, and Login Flows
- **Observation 1.2.1 (Registration Endpoint & Plan Provisioning)**: In `routers/auth.py` lines 55–93, `POST /api/saas/auth/register` validates `len(req.password.strip()) < 6`, provisions a `free` subscription with 3 credits, generates a JWT access token, and sets an HttpOnly cookie `saas_token` with `max_age=86400 * 30`.
- **Observation 1.2.2 (Authentication UI Modal)**: In `templates/index.html` lines 781–842, `auth-modal` hosts two tabs: `form-login` and `form-register`. Form inputs lack password visibility toggles (`type="password"` only) and password confirmation fields (`confirm_password`).
- **Observation 1.2.3 (Post-Registration State Update)**: In `templates/index.html` lines 3115–3120 (`handleRegister`):
  ```javascript
  closeAuthModal();
  await loadCurrentUser();
  await loadBlogs();
  await loadData();
  showToast('Pendaftaran berhasil! Akun Anda aktif dengan 3 kredit artikel gratis.', 'success');
  ```
- **Observation 1.2.4 (Superadmin Console Exposed to Guests)**: In `templates/index.html` lines 2981–2989:
  ```javascript
  const adminBtn = document.getElementById('btn-admin-console');
  if (adminBtn) {
    if (data.user && (data.user.role === 'admin' || data.user.email === 'admin@bagustech.id')) {
      adminBtn.classList.remove('hidden');
    } else {
      adminBtn.classList.add('hidden');
    }
  }
  ```
  Because unauthenticated calls to `/api/saas/auth/me` return `data.user` populated with `admin@bagustech.id` (Observation 1.1.4), anonymous visitors see the `"👑 Admin Console"` button in the primary header and can open `admin-modal`. Furthermore, `routers/admin.py` line 25 falls back to `default_admin`, allowing unauthenticated execution of admin operations.

---

### 1.3 Journey 3: Google Blogger OAuth Integration Flow & Permissions
- **Observation 1.3.1 (Modern Web 1-Click OAuth)**: In `routers/auth.py` lines 164–206, `GET /api/auth/google/login` builds an OAuth authorization URL using `google_auth_oauthlib.flow.Flow` with scope `https://www.googleapis.com/auth/blogger`, offline access (`access_type='offline'`), and encrypted state cookie (`bap_oauth_state`).
- **Observation 1.3.2 (Callback Auto-Import)**: In `routers/auth.py` lines 208–318, `GET /api/auth/google/callback` exchanges the auth code, writes credentials to `tokens/token_<uuid>.json`, encrypts credentials into `SaasBlog.encrypted_token`, queries `service.blogs().listByUser(userId='self')`, creates or updates `SaasBlog` records, and redirects to `/?auth_success=1&imported={imported_count}`.
- **Observation 1.3.3 (Bypassing Subscription Blog Limits on OAuth Import)**: In `routers/blogs.py` lines 96–103, manual blog registration enforces tier limits (`free: 1`, `starter: 3`, `pro: 10`, `agency: 50`). However, in `routers/auth.py` lines 286–307, `api_google_callback` iterates through all blogs returned by Google without validating `current_count < max_blogs`. A Free user with 5 Blogger accounts automatically imports all 5 blogs, bypassing tier gating.
- **Observation 1.3.4 (Tenant Blog Overwrite Vulnerability)**: In `routers/auth.py` line 288:
  ```python
  sb = saas_db.query(SaasBlog).filter(SaasBlog.id == b_id).first()
  ```
  The query matches exclusively by `Blog.id` without scoping by `user_id == session_u.id`. If a blog was previously registered or seeded under the default admin, the callback updates tokens and metadata on the existing record without reassigning `user_id`.
- **Observation 1.3.5 (Desktop / Manual OAuth Flow)**: In `routers/auth.py` lines 320–363, `/api/auth/url` and `/api/auth/exchange` use `InstalledAppFlow` with `redirect_uri='http://localhost'`. This requires users to manually copy a callback URL or authorization code from a browser window and paste it into `oauth-code-input`.

---

### 1.4 Journey 4: Blog Discovery, Selection, and Connection
- **Observation 1.4.1 (Hardcoded Header Metadata & Stale DOM State)**: In `templates/index.html` lines 225, 249, and 251, the template hardcodes:
  - Line 225: `<span id="active-blog-display-name">Bagus Tech</span>`
  - Line 249: `<strong ... id="active-blog-id">2940095957137948013</strong>`
  - Line 251: `<a id="active-blog-url" href="https://bagustechnologia.blogspot.com/" ...>`
- **Observation 1.4.2 (Zero-Blog Rendering Bailout Bug)**: In `templates/index.html` lines 1685–1698:
  ```javascript
  async function loadBlogs() {
    const res = await fetch('/api/blogs');
    blogs = await res.json();
    activeBlog = blogs.find(b => b.is_active === 1) || blogs[0] || null;
    renderBlogSelector();
  }
  function renderBlogSelector() {
    if (!activeBlog) return;
    ...
  ```
  For a newly registered user who has not connected a blog, `blogs` is `[]` and `activeBlog` is `null`. Because `renderBlogSelector()` aborts on `if (!activeBlog) return`, the hardcoded strings (`"Bagus Tech"`, `"2940095957137948013"`, `"bagustechnologia.blogspot.com"`) are never cleared or replaced. The new user sees another blog's identity prominently displayed in the header.
- **Observation 1.4.3 (Manual Blog ID Entry Friction)**: In `templates/index.html` lines 676–778 (`add-blog-modal`), adding a blog requires users to enter:
  1. `ID Blog Blogger *` ("Contoh: 8492019482019482019")
  2. `Nama Blog *`
  3. `URL Blog`
  4. `Nama Label Akun Google`
  5. `Niche / Topik Pembahasan`
- **Observation 1.4.4 (Hidden 1-Click OAuth Button)**: Inside `add-blog-modal` (lines 721–746), the radio option `"Satu Akun Google dengan Blog Aktif"` is checked by default. The 1-click Google OAuth button (`<a href="/api/auth/google/login">`) is hidden inside `#token-upload-area` (`class="hidden ..."`), which is only revealed if the user selects the second radio button (`"Akun Google Berbeda (Upload Token Baru)"`).

---

### 1.5 Journey 5: Autopilot Configuration
- **Observation 1.5.1 (Autopilot Settings Modal)**: In `templates/index.html` lines 1069–1118, `autopilot-modal` offers three configuration inputs:
  1. Background Autopilot Status (Checkbox toggle)
  2. Publish Mode (`blogger_draft`, `draft`, `published`)
  3. Schedule Frequency (`daily`, `twice_daily`, `manual`)
- **Observation 1.5.2 (Settings Storage)**: In `routers/blogs.py` lines 163–183, `POST /api/blogs/autopilot-settings` saves the configuration to a flat JSON file at `settings/autopilot_{blog.id}.json`.
- **Observation 1.5.3 (Daemon Disconnect & Fixed Hourly Loop)**: In `autopilot_scheduler.py` lines 23–148, the daemon loop runs at a fixed interval (`SCHEDULER_INTERVAL_SECONDS = 3600`, 1 hour). In `run_scheduler_cycle` (lines 38–116):
  - It does NOT read `settings/autopilot_{blog.id}.json`.
  - It does NOT check whether `schedule` is `daily`, `twice_daily`, or `manual`.
  - It invokes `generate_article(...)` directly.
- **Observation 1.5.4 (Hardcoded Draft Status in Generator)**: In `content_generator.py` line 470:
  ```python
  article = Article(
      user_id=user.id,
      blog_id=blog.id,
      title=title,
      target_keyword=kw.keyword,
      meta_description=meta_desc,
      content_html=content_html,
      labels=labels,
      status='draft'
  )
  ```
  `generate_article` always hardcodes `status='draft'` in the local database. The user's selection in the UI (`"Langsung Publikasikan Live ke Blogger"` or `"Kirim sebagai Draf di Blogger"`) is completely ignored by both the scheduler daemon and the content generator.
- **Observation 1.5.5 (Missing Tone & Style Configurations)**: Neither `autopilot-modal` nor `SaasBlog` contains fields for tone of voice (e.g. conversational, authoritative, journalistic). In `content_generator.py` lines 421–428, `user_prompt` uses fixed hardcoded instructions and ignores `blog.niche_description`.

---

### 1.6 Journey 6: Post Generation Trigger, Preview, Review, and Publishing
- **Observation 1.6.1 (Buat Draf AI Silent Failure on Empty Keywords)**:
  - User clicks `btn-auto-generate` (`templates/index.html` line 2835).
  - Client sends `POST /api/agent/generate-now` and receives `{'success': True}`.
  - Toast displays: `"Permintaan diterima! Draf artikel akan otomatis muncul di antrean saat siap."`
  - In `content_generator.py` lines 387–407, `generate_article` queries for a keyword with `status='planned'`.
  - If a new tenant has no keywords queued, line 403 returns:
    ```python
    return ArticleGenerationResult(
        success=False,
        blog_name=blog.name,
        error="Tidak ada keyword berstatus 'planned' yang tersedia."
    )
    ```
  - The client polls `/api/articles` every 10 seconds for 120 seconds. Since generation failed in the background worker, no article is created. After 120 seconds, the button resets to `"Buat Draf AI"` without any error message or notification.
- **Observation 1.6.2 (Fatal JavaScript Crash in "Tulis Manual")**: In `templates/index.html` lines 2375–2397:
  ```javascript
  function openNewArticleModal() {
    ...
    syncModalContent();
    updateCharCount();
    switchModalView('preview');
    updateSerpPreview(a.title, a.meta_description);
    document.getElementById('article-modal').classList.remove('hidden');
  }
  ```
  Variable `a` is not defined in `openNewArticleModal()`. When clicking `"Tulis Manual"`, the browser executes line 2395 and immediately throws `Uncaught ReferenceError: a is not defined`. Line 2396 is never reached; the modal fails to open.
- **Observation 1.6.3 (Fatal JavaScript Crash in "Sinkron Blogger")**: In `templates/index.html` lines 3268–3275:
  ```javascript
  const data = await res.json();
  if (data.success) {
    showToast(data.message, 'success');
    await loadArticles();
  } else { ... }
  ```
  The function `loadArticles()` does not exist (the application uses `loadData()`). When sync succeeds, JavaScript throws `ReferenceError: loadArticles is not defined`, triggering the catch block which displays: `showToast('Error sinkronisasi: loadArticles is not defined', 'error')`. The article queue is not refreshed.
- **Observation 1.6.4 (Article Publishing Flow)**: In `templates/index.html` lines 2425–2495 (`publishArticle`) and lines 2498–2554 (`quickPublish`), publishing sends `POST /api/articles/{id}/publish`.
  - Displays a confirmation modal (`showConfirm`).
  - Sets button spinner: `<span>Menghubungi Blogger...</span>` or `<span>Syncing...</span>`.
  - In `routers/articles.py` lines 126–233, injects Schema JSON-LD via `inject_schema_if_missing` and dispatches notification via `dispatch_notification`.
  - On response, updates status badge to `"Live di Blogger"` or `"Draft di Blogger"`.

---

### 1.7 Feedback Mechanisms, Interaction States & System Health
- **Observation 1.7.1 (Toast Suite Affordances)**: In `templates/index.html` lines 1482–1521, `showToast` renders non-blocking floating alerts with clear color coding (`emerald` for success, `rose` for error, `amber` for warning, `slate` for info).
- **Observation 1.7.2 (Custom Confirm & Prompt Modals)**: In `templates/index.html` lines 1524–1600, native browser `confirm()` and `prompt()` dialogs are replaced with accessible custom dialogs (`#confirm-modal` and `#prompt-modal`).
- **Observation 1.7.3 (Absence of Skeleton Loaders)**: During initial page load (`init()`), blog switching (`selectBlog()`), and filter changes, article lists render static plain text (`"Memuat draf artikel..."`, line 430) and keyword lists render `"Memuat keyword..."` (line 491). There are no skeleton screens or animated shimmer indicators.
- **Observation 1.7.4 (Ghost UI References)**: In `templates/index.html` line 2099:
  ```javascript
  list.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">Belum ada target keyword. Klik <b>⚡ Isi Ide SEO</b> atau <b>+ Tambah</b>.</div>`;
  ```
  The card header only contains `Import Massal`, `Ide Niche`, and `+ Tambah` (lines 485–487). There is no button labeled `"⚡ Isi Ide SEO"`. Furthermore, `autoGenerateKeywords()` (line 2665) looks for `document.getElementById('btn-auto-kw')`, which does not exist anywhere in `templates/index.html`.
- **Observation 1.7.5 (Global Knowledge Base Contamination)**: In `routers/settings.py` lines 50–96, `/api/kb/save`, `/api/kb/upload-pdf`, and `/api/prompt/save` read and write to global server files `seo_knowledge.md` and `seo_master_prompt.md`. When any tenant uploads a private PDF or edits the knowledge base, the content is injected into all other tenants' prompts and visible in their editor.

---

## 2. Logic Chain

```
[Observation 1.1.1, 1.1.2, 1.1.3]
  Root URL serves internal dashboard directly; marketing landing page is hidden in modal
        │
        ▼
  First-time visitor does not see value proposition, feature overview, or standard SaaS signup gate
        │
        ├──────────────────────────────────────────────────┐
        ▼                                                  ▼
[Observation 1.1.4, 1.2.4]                       [Observation 1.4.1, 1.4.2]
  Fallback to default admin tenant               Newly registered user has empty blogs [];
  grants anonymous visitor "Tamu (Mode Lokal)"   renderBlogSelector() aborts on null;
  and exposes "👑 Admin Console"                 DOM retains hardcoded "Bagus Tech" metadata
        │                                                  │
        ├──────────────────────────────────────────────────┘
        ▼
  Severe Cognitive Overload & Misdirection:
  New user believes an existing blog is already connected
        │
        ▼
[Observation 1.6.1]
  User clicks primary CTA "Buat Draf AI"
        │
        ▼
  Client receives 200 OK from /api/agent/generate-now
  Background worker aborts: no planned keywords exist in bank
  Client polls for 120s; button silently resets with zero articles and zero errors
        │
        ▼
[Observation 1.6.2]
  User attempts alternative CTA "Tulis Manual"
        │
        ▼
  Browser throws `ReferenceError: a is not defined` at index.html:2395
  Modal never opens; manual creation is 100% blocked
        │
        ▼
[Observation 1.4.3, 1.4.4]
  User attempts to connect their own blog via "+ Tambah Blog Baru"
        │
        ▼
  Modal defaults to "Satu Akun Google" and demands 19-digit Blogger Blog ID
  1-Click Google OAuth button is hidden behind unselected radio button
        │
        ▼
[Observation 1.6.3]
  If user successfully connects and syncs posts via "Sinkron Blogger"
        │
        ▼
  `syncBloggerPosts` executes `loadArticles()` (index.html:3270)
  Browser throws `ReferenceError: loadArticles is not defined`
  Error toast immediately flashes over success toast
        │
        ▼
[Observation 1.5.3, 1.5.4]
  If user configures Autopilot scheduling
        │
        ▼
  Daemon ignores frequency (runs hourly) and ignores publish_mode (hardcodes 'draft')
        │
        ▼
  CRITICAL ONBOARDING DROP-OFF & RETENTION FAILURE:
  Time-to-first-value is completely obstructed by silent background failures,
  runtime JavaScript errors, and missing onboarding scaffolding.
```

---

## 3. Caveats
1. **Google Cloud OAuth Production Domain Verification**: In local testing, OAuth relies on `http://localhost:8090/api/auth/google/callback` or `http://localhost:3000/api/auth/callback/blogger`. In production, Google Cloud Console requires strict domain verification and HTTPS redirect URIs.
2. **LLM API Provider Credentials**: If `GEMINI_API_KEY` or `OPENAI_API_KEY` is not present in `.env`, `content_generator.py` falls back to `StructuredFallbackAdapter` (`generate_structured_fallback_article`), which generates structured mock content. The silent keyword failure occurs prior to LLM adapter execution.
3. **Midtrans Sandbox Mode**: Payment flows were audited based on Snap token creation, mock demo fallbacks, and webhook schemas. Physical credit card transactions depend on Midtrans sandbox availability.

---

## 4. Conclusion & Prioritized Strategic Recommendations

The Blogger Auto-Pilot SaaS application possesses powerful underlying capabilities (automated E-E-A-T Schema generation, 1-click Google OAuth blog sync, Midtrans payment integration, and background daemon execution). However, **the user journey and onboarding experience suffer from critical architectural and frontend blockers that prevent first-time users from reaching their first published post.**

### Audit Finding Matrix & Severity Summary

| ID | Journey Stage | Finding Description | Severity | Impact |
|:---|:---|:---|:---:|:---|
| **F-01** | Arrival / Landing | Root route `/` bypasses marketing landing page; `#landing-preview-modal` is hidden by default | **P0** | High bounce rate; no public value proposition |
| **F-02** | Security / Auth | Unauthenticated guest inherits admin tenant and sees `"👑 Admin Console"` | **P0** | Severe multi-tenant security vulnerability & UX confusion |
| **F-03** | Studio / Header | Zero-blog state fails to clear hardcoded "Bagus Tech" metadata | **P0** | User believes wrong blog is active |
| **F-04** | Content Creation | "Tulis Manual" crashes with `ReferenceError: a is not defined` (`index.html:2395`) | **P0** | Feature completely unusable |
| **F-05** | Blog Sync | "Sinkron Blogger" crashes with `ReferenceError: loadArticles is not defined` (`index.html:3270`) | **P0** | Post-sync error toast; table does not reload |
| **F-06** | AI Generation | "Buat Draf AI" silently fails in background worker when keyword bank is empty | **P0** | 120s false loading state followed by silent failure |
| **F-07** | Blog Connection | 1-Click Google OAuth button hidden inside nested radio panel; requires manual 19-digit Blog ID | **P1** | Excessive onboarding friction for non-technical bloggers |
| **F-08** | Autopilot Scheduler | Scheduler daemon runs hourly and hardcodes `status='draft'`, ignoring UI frequency and publish mode | **P1** | Autopilot settings in UI do not take effect |
| **F-09** | Knowledge Base | Global file write (`seo_knowledge.md`) causes multi-tenant data cross-contamination | **P1** | Tenant privacy leak; lack of per-blog customization |
| **F-10** | UI / Interaction | Missing skeleton screens; empty keyword state references ghost button `"⚡ Isi Ide SEO"` | **P2** | Polish & usability deficit |

---

### Prioritized Tactical Execution Plan

#### P0 — Immediate Launch Blockers (Must Fix Before Any Public Traffic)
1. **Fix Fatal JavaScript Runtime Crashes**:
   - `templates/index.html:2395`: In `openNewArticleModal()`, change `updateSerpPreview(a.title, a.meta_description);` to `updateSerpPreview('', '');`.
   - `templates/index.html:3270`: In `syncBloggerPosts()`, change `await loadArticles();` to `await loadData();`.
2. **Seal Authentication Gate & Remove Guest Admin Fallback**:
   - In `dependencies.py` and `routers/auth.py`, return `authenticated: false` and `user: null` when `saas_token` is missing or invalid.
   - Do NOT fall back to `admin@bagustech.id` on public requests.
   - If not authenticated, redirect `/` to `/login` or render `#landing-preview-modal` directly as the default landing page.
3. **Fix Zero-Blog Header Rendering**:
   - In `templates/index.html:1696` (`renderBlogSelector`), handle `if (!activeBlog)`:
     ```javascript
     if (!activeBlog) {
       document.getElementById('active-blog-display-name').innerText = 'Belum Ada Blog';
       document.getElementById('active-blog-id').innerText = '-';
       document.getElementById('active-blog-url').innerText = 'Hubungkan Blog ↗';
       document.getElementById('active-blog-autopilot-label').innerText = 'Autopilot: Nonaktif';
       document.getElementById('blog-total-badge').innerText = '0 Blog';
       return;
     }
     ```
4. **Prevent Silent Failure on "Buat Draf AI"**:
   - In `routers/articles.py:245` (`api_agent_generate_now`), check if tenant has at least 1 planned keyword before dispatching background task. If not, return HTTP 400 with actionable error: `"Bank keyword Anda masih kosong. Tambahkan minimal 1 keyword atau gunakan 'Ide Niche' terlebih dahulu."`
   - Alternatively, automatically generate a seed keyword from the blog's niche if the bank is empty.

#### P1 — Essential Onboarding & Experience Enhancements
1. **Guided 3-Step First-Time Onboarding Wizard**:
   - Replace the manual 19-digit Blog ID prompt with a prominent **"Hubungkan Akun Google Blogger (1-Klik)"** banner.
   - Step 1: Connect Google Account (auto-imports blogs).
   - Step 2: Select Niche & Auto-Generate 5 Seed Keywords.
   - Step 3: Click "Generate First Post" with real-time SSE / progress bar.
2. **Align Autopilot Daemon with UI Settings**:
   - Update `autopilot_scheduler.py` to read `settings/autopilot_{blog.id}.json`.
   - Respect `publish_mode`: if `published`, call `create_post(..., is_draft=False)`; if `blogger_draft`, call `create_post(..., is_draft=True)`.
3. **Tenant-Isolate Knowledge Base & Prompts**:
   - Migrate `seo_knowledge` and `seo_master_prompt` from global filesystem files into the database (`models_saas.Blog` or new `TenantKnowledgeBase` model).

#### P2 — Post-Launch Polish & Delight
1. **Visual Skeletons & Shimmer States**: Add animated Tailwind pulse cards during `loadData()` and `syncBloggerPosts()`.
2. **Clean Up UI Ghost References**: Remove reference to `"⚡ Isi Ide SEO"` in `renderKeywords()` and replace with actionable link opening `openAiSuggestModal()`.

---

## 5. Verification Method

### 5.1 Independent Code Verification
1. **Inspect "Tulis Manual" crash**:
   - Open `/Users/mac/Documents/projects/blogger-autopilot/templates/index.html` at line 2395.
   - Verify call to `updateSerpPreview(a.title, a.meta_description)` inside `openNewArticleModal()` without declaration of `a`.
2. **Inspect "Sinkron Blogger" crash**:
   - Open `/Users/mac/Documents/projects/blogger-autopilot/templates/index.html` at line 3270.
   - Verify call to `loadArticles()`. Search for `function loadArticles` across the codebase (0 results).
3. **Inspect Anonymous Admin Fallback & Console Visibility**:
   - View `/Users/mac/Documents/projects/blogger-autopilot/routers/auth.py` line 133 (`get_or_create_default_admin(db)`).
   - View `/Users/mac/Documents/projects/blogger-autopilot/templates/index.html` line 2984 (`data.user.role === 'admin'`).

### 5.2 Verification Commands
To verify the application runtime and existing test suite:
```bash
# Verify test suite passing state
pytest test_saas_full_flow.py test_multitenant_crud.py test_new_saas_features.py -v

# Check presence of client_secret.json
ls -la client_secret.json

# Check unauthenticated /api/saas/auth/me response
curl -s http://127.0.0.1:8090/api/saas/auth/me
```

### 5.3 Invalidation Conditions
This report is invalidated if:
1. Routing in `app.py` is updated to mount a dedicated public landing controller on `GET /` and moves the studio dashboard behind authentication middleware.
2. The runtime bugs at `index.html:2395` and `index.html:3270` are resolved.
3. The background worker implements an active job status polling endpoint or websocket feed.
