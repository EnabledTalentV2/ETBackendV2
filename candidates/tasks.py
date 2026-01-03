# candidates/tasks.py

import requests
import tempfile
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import CandidateProfile
from .resume_parser import parse_resume


@shared_task(bind=True, max_retries=3, time_limit=1800, soft_time_limit=1500)
def parse_resume_task(self, candidate_profile_id):
    """
    Background task to parse a resume stored in Supabase (public URL).
    1. Fetch CandidateProfile.
    2. Download resume from Supabase URL.
    3. Save to a temp file.
    4. Run parse_resume(temp_path).
    5. Save parsed data on the candidate.
    """
    candidate = None

    try:
        print(f"[Celery] Starting resume parsing for candidate {candidate_profile_id}")

        # Fetch candidate
        candidate = CandidateProfile.objects.get(id=candidate_profile_id)

        # Ensure a resume URL exists
        if not candidate.resume_file:
            candidate.parsing_status = "failed"
            candidate.save(update_fields=["parsing_status"])
            return {"status": "failed", "error": "No resume file URL set"}

        # Mark as parsing
        candidate.parsing_status = "parsing"
        candidate.save(update_fields=["parsing_status"])

        resume_url = candidate.resume_file
        print(f"[Celery] Downloading resume from: {resume_url}")

        # ---------------------------------------------------------
        # 1) Download resume from Supabase public URL
        # ---------------------------------------------------------
        resp = requests.get(resume_url, timeout=60)

        if resp.status_code != 200:
            raise Exception(f"Failed to download resume: HTTP {resp.status_code}")

        # ---------------------------------------------------------
        # 2) Write to a temporary file (for parsers expecting a path)
        # ---------------------------------------------------------
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        print(f"[Celery] Temporary resume file created at {tmp_path}")

        # ---------------------------------------------------------
        # 3) Parse resume using existing parser (expects a file path)
        # ---------------------------------------------------------
        parsed_obj = parse_resume(tmp_path)

        # Support both Pydantic model and plain dict
        if hasattr(parsed_obj, "model_dump"):
            resume_data = parsed_obj.model_dump()
        else:
            resume_data = parsed_obj

        # ---------------------------------------------------------
        # 4) Save parsed data back to candidate
        # ---------------------------------------------------------
        candidate.resume_data = resume_data
        candidate.parsing_status = "parsed"
        candidate.save(update_fields=["resume_data", "parsing_status"])

        print(f"[Celery] Resume parsed successfully for candidate {candidate_profile_id}")
        return {"status": "success", "data": resume_data}

    except Exception as exc:
        print(f"[Celery] ERROR parsing resume for candidate {candidate_profile_id}: {exc}")

        # Mark as failed if candidate still exists
        if candidate:
            candidate.parsing_status = "failed"
            candidate.save(update_fields=["parsing_status"])

        # Retry if we haven't hit max retries yet
        if self.request.retries < self.max_retries:
            delay = 60 * (self.request.retries + 1)
            print(f"[Celery] Retrying in {delay} seconds...")
            raise self.retry(countdown=delay)

        return {"status": "failed", "error": str(exc)}


@shared_task
def cleanup_failed_parsing_tasks():
    """
    Reset records stuck in 'parsing' for more than 1 hour back to 'not_parsed'.
    Requires CandidateProfile.updated_at (auto_now=True).
    """
    print("[Celery] Running cleanup_failed_parsing_tasks")

    one_hour_ago = timezone.now() - timedelta(hours=1)

    stuck = CandidateProfile.objects.filter(
        parsing_status="parsing",
        updated_at__lt=one_hour_ago,
    )

    count = stuck.count()
    stuck.update(parsing_status="not_parsed")

    print(f"[Celery] Reset parsing_status='not_parsed' for {count} candidates")
    return {"reset_count": count}
