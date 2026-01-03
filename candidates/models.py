# candidates/models.py

from django.db import models
from django.utils.text import slugify
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from users.models import User
from organization.models import Organization
from openai import OpenAI
import uuid

client = OpenAI()

NEEDS = (
    ("YES", "YES"),
    ("NO", "NO"),
    ("PREFER_TO_DISCUSS_LATER", "PREFER_TO_DISCUSS_LATER"),
)

DISCLOSURE_PREFERENCE = (
    ("DURING_APPLICATION", "DURING_APPLICATION"),
    ("DURING_INTERVIEW", "DURING_INTERVIEW"),
    ("AFTER_JOB_OFFER", "AFTER_JOB_OFFER"),
    ("AFTER_STARTING_WORK", "AFTER_STARTING_WORK"),
    ("NOT_APPLICABLE", "NOT_APPLICABLE"),
)


class CandidateProfile(models.Model):
    PARSING_STATUS = (
        ("not_parsed", "Not Parsed"),
        ("parsing", "Parsing In Progress"),
        ("parsed", "Parsed Successfully"),
        ("failed", "Parsing Failed"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, blank=True, null=True
    )

    # FILES NOW STORED IN SUPABASE → store the PUBLIC URL
    resume_file = models.URLField(max_length=500, blank=True, null=True)
    video_pitch = models.URLField(max_length=500, blank=True, null=True)

    resume_data = models.JSONField(blank=True, null=True)
    parsing_status = models.CharField(
        max_length=20, choices=PARSING_STATUS, default="not_parsed"
    )

    willing_to_relocate = models.BooleanField(default=True)

    employment_type_preferences = models.JSONField(default=list)
    work_mode_preferences = models.JSONField(default=list)
    has_workvisa = models.BooleanField(default=False)
    disability_categories = models.JSONField(default=list)
    accommodation_needs = models.CharField(max_length=100, choices=NEEDS)
    disclosure_preference = models.CharField(
        max_length=100, choices=DISCLOSURE_PREFERENCE
    )
    workplace_accommodations = models.JSONField(default=list)

    expected_salary_range = models.CharField(max_length=20, blank=True, null=True)

    is_available = models.BooleanField(default=True)

    # Tracking
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CandidateProfile({self.user.email})"

    @property
    def get_all_notes(self):
        return self.notes.all()

    def save(self, *args, **kwargs):
        if not self.slug:
            # safer & collision-proof
            base = slugify(self.user.email.split("@")[0])
            self.slug = f"{base}-{uuid.uuid4().hex[:8]}"

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["organization", "id"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["parsing_status"]),
            models.Index(fields=["is_available"]),
        ]


class Notes(models.Model):
    resume = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="notes"
    )

    identifier = models.CharField(max_length=255)
    section = models.TextField(blank=True, null=True)
    selected_text = models.TextField(blank=True, null=True)
    context = models.JSONField(blank=True, null=True)
    note = models.CharField(max_length=100)

    # SUPABASE public URL
    note_file = models.URLField(max_length=500, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.note


# =======================
# LLM Conversation Helpers
# =======================

# In-memory threads
conversation_threads = {}


def get_resume_context(resume_slug, user_query, thread_id=None, messages=None):
    profile = get_object_or_404(CandidateProfile, slug=resume_slug)
    notes = "\n".join(n.note for n in profile.notes.all())

    if not messages:
        messages = [
            {
                "role": "system",
                "content": f"""
                You are a helpful assistant summarizing a resume.
                Resume: {profile.resume_data}
                Notes: {notes or "No notes yet"}
                """,
            }
        ]

    messages.append({"role": "user", "content": user_query})

    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    msg = response.choices[0].message

    messages.append({"role": "assistant", "content": msg.content})

    return {"response": msg.content, "thread_id": thread_id, "messages": messages}


def get_career_coach(resume_slug, user_query, thread_id=None, messages=None):
    profile = get_object_or_404(CandidateProfile, slug=resume_slug)
    notes = "\n".join(n.note for n in profile.notes.all())

    if not messages:
        messages = [
            {
                "role": "system",
                "content": f"""
                You are a friendly career coach.
                Resume: {profile.resume_data}
                Notes: {notes or "No notes yet"}
                """,
            }
        ]

    messages.append({"role": "user", "content": user_query})

    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    msg = response.choices[0].message

    messages.append({"role": "assistant", "content": msg.content})

    return {"response": msg.content, "thread_id": thread_id, "messages": messages}
