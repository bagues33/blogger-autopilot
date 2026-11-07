"""
Autopilot Scheduler Daemon for Blogger Auto-Pilot SaaS
Runs periodic background cycles to generate articles for subscribers with active plans and remaining credits.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db_saas import SessionLocal
from models_saas import User, Subscription, Blog, Article, Keyword
from content_generator import generate_article

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [AutopilotScheduler] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AutopilotScheduler")

SCHEDULER_INTERVAL_SECONDS = int(os.environ.get('SCHEDULER_INTERVAL_SECONDS', '3600')) # Default: 1 hour

def run_scheduler_cycle(max_per_cycle: int = 5) -> dict:
    """
    Executes one autonomous cycle across all active tenants.
    Finds subscribers with remaining credits, picks their active blog and next keyword,
    and runs the autonomous AI generation worker.
    """
    logger.info("Starting Autopilot Scheduler cycle...")
    db: Session = SessionLocal()
    processed_count = 0
    results = []

    try:
        # Find active subscriptions with available quota
        active_subs = db.query(Subscription).filter(
            Subscription.status == 'active',
            Subscription.article_credits_used < Subscription.article_credits_limit
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

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        result = run_scheduler_cycle()
        print(f"Cycle result: {result}")
    else:
        interval = SCHEDULER_INTERVAL_SECONDS
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            interval = int(sys.argv[1])
        start_scheduler_loop(interval)
