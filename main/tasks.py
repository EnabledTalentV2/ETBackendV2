from celery import shared_task
from django.core.cache import cache
from .models import JobPost
from .jobpost_candidate_ranker import ranking_algo
from django.utils import timezone
from datetime import timedelta


@shared_task(bind=True, max_retries=3, time_limit=1800, soft_time_limit=1500)
def rank_candidates_task(self, job_id):
    """
    Background task that runs the candidate ranking algorithm 
    and stores results inside JobPost.candidate_ranking_data
    """
    try:
        print(f"[RANKING] Starting ranking task for job {job_id}")

        # Load job post safely with prefetch
        job_post = JobPost.objects.select_related(
            "user", "organization"
        ).prefetch_related("skills").get(id=job_id)

        # Mark it as "ranking"
        job_post.ranking_status = "ranking"
        job_post.save(update_fields=["ranking_status"])

        # Run ranking logic
        result = ranking_algo(job_id)

        # Save results
        job_post.candidate_ranking_data = {
            "ranked_candidates": result.get("ranked_candidates", []),
            "token_usage": result.get("token_usage", {}),
            "estimated_cost": result.get("estimated_cost", 0),
            "last_updated": result.get("last_updated", str(timezone.now())),
        }
        job_post.ranking_status = "ranked"
        job_post.save(update_fields=["candidate_ranking_data", "ranking_status"])

        # Invalidate cache
        cache_key = f"job_ranking_data_{job_id}"
        cache.delete(cache_key)

        print(f"[RANKING] Completed ranking job {job_id}")

        return {
            "status": "success",
            "job_id": job_id,
            "ranked_candidates_count": len(
                result.get("ranked_candidates", [])
            ),
            "total_cost": result.get("estimated_cost", 0),
        }

    except Exception as exc:
        print(f"[RANKING] Failed for job {job_id}: {str(exc)}")

        # Mark job as failed
        try:
            job_post = JobPost.objects.get(id=job_id)
            job_post.ranking_status = "failed"
            job_post.save(update_fields=["ranking_status"])
        except JobPost.DoesNotExist:
            print(f"[RANKING] Could not update job status: job not found")

        # Retry if allowed
        if self.request.retries < self.max_retries:
            print(f"[RANKING] Retrying job {job_id}...")
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {"status": "failed", "error": str(exc)}



@shared_task
def cleanup_failed_ranking_tasks():
    """
    Resets jobs that got stuck in 'ranking' for too long.
    Uses created_at since JobPost has NO updated_at field.
    """
    print("[CLEANUP] Cleaning stuck ranking tasks...")

    cutoff_time = timezone.now() - timedelta(hours=2)

    stuck_jobs = JobPost.objects.filter(
        ranking_status="ranking",
        created_at__lt=cutoff_time,  # fallback since updated_at does not exist
    )

    count = stuck_jobs.count()
    stuck_jobs.update(ranking_status="not_ranked", ranking_task_id=None)

    print(f"[CLEANUP] Reset {count} stuck ranking jobs")

    return {"reset_count": count}
