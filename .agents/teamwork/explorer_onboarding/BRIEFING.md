# BRIEFING — 2026-11-07T10:28:00Z

## Mission
Conduct a rigorous, evidence-based audit of user journeys, onboarding, and workflow experience across the Blogger Auto-Pilot SaaS application.

## 🔒 My Identity
- Archetype: explorer
- Roles: User Journeys & Onboarding Auditor
- Working directory: /Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding
- Original parent: c6ec4876-3792-4539-9c02-3531835f6954
- Milestone: Onboarding & User Journey Audit

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Inspect routes, controllers, templates, OAuth handlers, and scheduling logic
- Cite exact file paths, line numbers, and code snippets as evidence
- Produce a structured, comprehensive handoff report at .agents/teamwork/explorer_onboarding/handoff.md
- Maintain liveness via progress.md
- Send completion message to orchestrator via send_message when finished

## Current Parent
- Conversation ID: c6ec4876-3792-4539-9c02-3531835f6954
- Updated: 2026-11-07T10:28:00Z

## Investigation State
- **Explored paths**:
  - `app.py`: Root HTML handler, router mounts, dependency injection
  - `routers/auth.py`: Registration, login, logout, me endpoint, Google OAuth web/desktop endpoints
  - `routers/blogs.py`: Blog listing, selection, addition, deletion, autopilot settings, post syncing
  - `routers/articles.py`: Article CRUD, publishing, on-demand generation trigger, image upload
  - `routers/keywords.py`: Keyword bank, bulk addition, AI template suggest, deletion
  - `routers/billing.py`: Midtrans Snap token generation, demo upgrade, webhook handling
  - `routers/settings.py`: Knowledge base, prompt saving, PDF upload, notification settings
  - `routers/admin.py`: Superadmin metrics, tenant management, require_admin fallback
  - `content_generator.py`: LLM generation pipeline, tenant quota check, keyword resolution, silent errors
  - `autopilot_scheduler.py`: Daemon loop, tenant batch processing, fixed interval vs UI disconnect
  - `templates/index.html`: Complete frontend DOM, 12 modals, JavaScript SPA logic (3681 lines)
- **Key findings**:
  1. Root `/` serves internal studio dashboard directly; marketing landing page is hidden in modal `#landing-preview-modal` (accessible only via `?landing=1` or menu).
  2. Unauthenticated visitors are treated as "Tamu (Mode Lokal)" via `get_or_create_default_admin`, exposing Superadmin's blogs, articles, and even the "👑 Admin Console" button.
  3. Newly registered tenants receive empty blog list, but UI DOM retains hardcoded "Bagus Tech" and blog ID `2940095957137948013` due to early return in `renderBlogSelector()`.
  4. Fatal JS Crash in "Tulis Manual" (`openNewArticleModal()` line 2395): calls `updateSerpPreview(a.title, a.meta_description)` where `a` is undefined (`ReferenceError: a is not defined`).
  5. Fatal JS Crash in "Sinkron Blogger" (`syncBloggerPosts()` line 3270): calls `await loadArticles()` which does not exist (`ReferenceError: loadArticles is not defined`).
  6. Silent background task failure on "Buat Draf AI": if keyword bank is empty, `generate_article` fails in background, but user sees toast "Permintaan diterima...", button polls for 120s, and resets without error.
  7. Autopilot UI vs Daemon Disconnect: UI allows selecting `publish_mode` and `schedule` (`daily`, `twice_daily`), but scheduler daemon and `generate_article` hardcode `status='draft'` and run on a single global hourly loop.
  8. Knowledge base & master prompt are global flat files (`seo_knowledge.md`), causing multi-tenant cross-contamination when any user edits or uploads PDFs.
  9. Ghost UI references: empty keyword state instructs user to click "⚡ Isi Ide SEO", but button `btn-auto-kw` does not exist in the DOM.
  10. Time-to-first-post friction: no onboarding wizard, no guided setup checklist, manual 19-digit blog ID requirement, hidden 1-click Google OAuth button.
- **Unexplored areas**: None. Complete audit of all 6 journeys, interaction feedback states, and onboarding drop-off risks accomplished.

## Key Decisions Made
- Completed systematic code inspection across all frontend and backend touchpoints.
- Prepared evidence-based synthesis for handoff report.

## Artifact Index
- /Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding/DISPATCH.md — Dispatch log
- /Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding/BRIEFING.md — Persistent memory
- /Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding/progress.md — Heartbeat and progress tracker
- /Users/mac/Documents/projects/blogger-autopilot/.agents/teamwork/explorer_onboarding/handoff.md — Final handoff report
