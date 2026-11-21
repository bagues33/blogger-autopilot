"""
Autopilot Scheduler Daemon for Blogger Auto-Pilot SaaS
Runs periodic background cycles to generate articles for subscribers with active plans and remaining credits.
Supports standalone daemon loops, one-shot cron jobs, dry-run simulations, and queue status reports.
"""

import os
import sys
import time
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models.models import User, Subscription, Blog, Article, Keyword
from src.services.content_generator import generate_article

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [AutopilotScheduler] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AutopilotScheduler")

SCHEDULER_INTERVAL_SECONDS = int(os.environ.get('SCHEDULER_INTERVAL_SECONDS', '3600')) # Default: 1 hour

def get_scheduler_status(db: Optional[Session] = None) -> dict:
    """
    Returns current health and queue metrics of the Autopilot daemon.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        active_subs_count = db.query(Subscription).join(User).filter(
            Subscription.status == 'active',
            Subscription.article_credits_used < Subscription.article_credits_limit,
            (Subscription.plan_tier.in_(['pro', 'agency'])) | (User.role == 'admin')
        ).count()
        autopilot_blogs_count = db.query(Blog).filter(
            (Blog.autopilot_enabled == True) | (Blog.is_active == 1)
        ).count()
        planned_kws_count = db.query(Keyword).filter(
            Keyword.status == 'planned'
        ).count()
        total_articles_count = db.query(Article).count()
        published_count = db.query(Article).filter(Article.status == 'published').count()
        return {
            'active_eligible_subscriptions': active_subs_count,
            'autopilot_blogs_configured': autopilot_blogs_count,
            'planned_keywords_in_queue': planned_kws_count,
            'total_articles': total_articles_count,
            'published_articles': published_count,
            'cycle_interval_seconds': SCHEDULER_INTERVAL_SECONDS
        }
    finally:
        if close_db:
            db.close()

def run_scheduler_cycle(max_per_cycle: int = 5, force: bool = False, dry_run: bool = False) -> dict:
    """
    Executes one autonomous cycle across all active tenants.
    Finds subscribers with remaining credits, picks their active blog and next keyword,
    and runs the autonomous AI generation worker.

    Args:
        max_per_cycle: Maximum articles to draft in one execution cycle.
        force: If True, bypasses frequency threshold (min_elapsed check).
        dry_run: If True, simulates selection without invoking LLM or mutating database.
    """
    mode_str = "DRY-RUN SIMULATION" if dry_run else ("FORCE RUN" if force else "STANDARD RUN")
    logger.info(f"Starting Autopilot Scheduler cycle ({mode_str}, max_per_cycle={max_per_cycle})...")
    db: Session = SessionLocal()
    processed_count = 0
    results = []

    try:
        # Find active subscriptions with available quota for Pro / Agency / Admin
        active_subs = db.query(Subscription).join(User).filter(
            Subscription.status == 'active',
            Subscription.article_credits_used < Subscription.article_credits_limit,
            (Subscription.plan_tier.in_(['pro', 'agency'])) | (User.role == 'admin')
        ).all()

        logger.info(f"Found {len(active_subs)} active subscription(s) eligible for autopilot generation.")

        for sub in active_subs:
            if processed_count >= max_per_cycle:
                logger.info(f"Reached batch limit ({max_per_cycle}) for this cycle. Remaining deferred to next cycle.")
                break

            user = sub.user
            if not user or not user.is_active:
                continue

            # Query all active user blogs up to their plan limit
            max_blogs = {'free': 1, 'starter': 3, 'pro': 10, 'agency': 50}.get(sub.plan_tier, 1)
            user_blogs = (
                db.query(Blog)
                .filter(Blog.user_id == user.id)
                .order_by(Blog.is_active.desc(), Blog.created_at.asc())
                .limit(max_blogs)
                .all()
            )

            if not user_blogs:
                logger.debug(f"User {user.email} has no registered blog. Skipping.")
                continue

            for blog in user_blogs:
                if processed_count >= max_per_cycle:
                    break
                if sub.article_credits_used >= sub.article_credits_limit:
                    logger.info(f"User {user.email} reached credit limit ({sub.article_credits_used}/{sub.article_credits_limit}). Skipping further blogs.")
                    break

                # Check autopilot enablement
                if hasattr(blog, 'autopilot_enabled') and blog.autopilot_enabled is False and blog.is_active != 1:
                    logger.debug(f"Blog '{blog.name}' has autopilot disabled. Skipping.")
                    continue

                # Check schedule frequency eligibility (bypassed if force=True)
                if not force and getattr(blog, 'last_run_at', None) and getattr(blog, 'schedule_frequency', None):
                    now_utc = datetime.now(timezone.utc)
                    last_utc = blog.last_run_at if blog.last_run_at.tzinfo else blog.last_run_at.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc - last_utc).total_seconds()
                    min_elapsed = {'hourly': 3600, 'twice_daily': 43200, 'daily': 86400}.get(blog.schedule_frequency, 86400)
                    if elapsed < min_elapsed:
                        logger.debug(f"Blog '{blog.name}' schedule '{blog.schedule_frequency}' not yet due ({int(elapsed)}s < {min_elapsed}s). Skipping.")
                        continue

                # Find planned keyword for this user and blog
                kw = db.query(Keyword).filter(
                    Keyword.user_id == user.id,
                    Keyword.blog_id == blog.id,
                    Keyword.status == 'planned'
                ).order_by(Keyword.id.asc()).first()

                if not kw:
                    # Check keywords without specific blog_id
                    kw = db.query(Keyword).filter(
                        Keyword.user_id == user.id,
                        Keyword.blog_id.is_(None),
                        Keyword.status == 'planned'
                    ).order_by(Keyword.id.asc()).first()

                if not kw:
                    logger.debug(f"User {user.email} has no 'planned' keywords queued for blog '{blog.name}'. Skipping.")
                    continue

                if dry_run:
                    processed_count += 1
                    logger.info(f"[SIMULATION] Would generate article for {user.email} | Blog: {blog.name} | Keyword: '{kw.keyword}'")
                    results.append({
                        'user_id': user.id,
                        'email': user.email,
                        'blog_id': blog.id,
                        'keyword': kw.keyword,
                        'status': 'simulated'
                    })
                    continue

                logger.info(f"Executing Autopilot for User: {user.email} (Plan: {sub.plan_tier}) | Blog: {blog.name} | Keyword: '{kw.keyword}'")
                try:
                    # Trigger autonomous generation for this specific tenant user, blog, and keyword
                    res = generate_article(
                        tenant_id=user.id,
                        blog_id=blog.id,
                        keyword_id=kw.id,
                        db=db
                    )
                    if res.success:
                        processed_count += 1
                        blog.last_run_at = datetime.now(timezone.utc)
                        db.commit()
                        results.append({
                            'user_id': user.id,
                            'email': user.email,
                            'blog_id': blog.id,
                            'keyword': kw.keyword,
                            'status': 'success',
                            'article_id': res.article_id
                        })
                    else:
                        logger.error(f"Error running content generator for {user.email}: {res.error}")
                        results.append({
                            'user_id': user.id,
                            'email': user.email,
                            'blog_id': blog.id,
                            'keyword': kw.keyword,
                            'error': res.error,
                            'status': 'failed'
                        })
                except Exception as e:
                    logger.error(f"Unexpected error running content generator for {user.email}: {e}")
                    results.append({
                        'user_id': user.id,
                        'email': user.email,
                        'blog_id': blog.id,
                        'error': str(e),
                        'status': 'failed'
                    })

        return {
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'dry_run': dry_run,
            'force': force,
            'processed_count': processed_count,
            'details': results
        }
    finally:
        db.close()

def start_scheduler_loop(interval_seconds: int = SCHEDULER_INTERVAL_SECONDS):
    logger.info(f"Autopilot Scheduler Daemon started (Cycle Interval: {interval_seconds}s)")
    try:
        while True:
            try:
                res = run_scheduler_cycle()
                logger.info(f"Cycle completed: {res.get('processed_count', 0)} article(s) drafted.")
            except Exception as e:
                logger.error(f"Unexpected error in cycle: {e}")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Autopilot Scheduler stopped by user.")

def print_help():
    print("""
Blogger Auto-Pilot Scheduler Daemon
Commands & Options:
  --status         Print current Autopilot queue metrics and eligible subscriptions
  --dry-run        Simulate one execution cycle without generating content or mutating database
  --once           Execute one cycle immediately and terminate
  --force          Execute one cycle bypassing frequency limits (min_elapsed)
  --interval <sec> Run continuous daemon loop with custom sleep interval in seconds
  --help           Show this help message
""")

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--help' in args or '-h' in args:
        print_help()
    elif '--status' in args:
        status = get_scheduler_status()
        print("\n--- Blogger Auto-Pilot Daemon Status ---")
        for k, v in status.items():
            print(f"  {k:35}: {v}")
        print("----------------------------------------\n")
    elif '--dry-run' in args:
        result = run_scheduler_cycle(dry_run=True, force='--force' in args)
        print(f"Dry-run simulation result: {result}")
    elif '--once' in args:
        result = run_scheduler_cycle(force='--force' in args)
        print(f"One-shot cycle result: {result}")
    else:
        interval = SCHEDULER_INTERVAL_SECONDS
        for i, a in enumerate(args):
            if a in ('--interval', '-i') and i + 1 < len(args) and args[i+1].isdigit():
                interval = int(args[i+1])
            elif a.isdigit():
                interval = int(a)
        start_scheduler_loop(interval)
