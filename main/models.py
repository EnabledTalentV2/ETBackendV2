from django.db import models
import uuid
# Create your models here.
from django.db import models
from django.conf import settings
from organization.models import Organization
from dotenv import load_dotenv

load_dotenv()


WORKPLACE_TYPES = (
    (1, 'Hybrid'),
    (2, 'On-Site'),
    (3, 'Remote'),
)

WORK_TYPES = (
    (1, 'Full-time'),
    (2, 'Part-time'),
    (3, 'Contract'),
    (4, 'Temporary'),
    (5, 'Other'),
    (6, 'Volunteer'),
    (7, 'Internship'),
)


class Skills(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Skills'
        verbose_name_plural = 'Skills'


class JobPost(models.Model):
    RANKING_STATUS = (
        ('not_ranked', 'Not Ranked'),
        ('ranking', 'Ranking in Progress'),
        ('ranked', 'Ranked Successfully'),
        ('failed', 'Ranking Failed'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    title = models.CharField(max_length=100)
    job_desc = models.TextField()
    workplace_type = models.IntegerField(choices=WORKPLACE_TYPES)
    location = models.CharField(max_length=100)
    job_type = models.IntegerField(choices=WORK_TYPES)
    skills = models.ManyToManyField(Skills)
    estimated_salary = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   # ✅ add this

    visa_required = models.BooleanField(default=False)
    candidate_ranking_data = models.JSONField(null=True, blank=True)
    ranking_status = models.CharField(
        max_length=20, choices=RANKING_STATUS, default='not_ranked'
    )
    ranking_task_id = models.CharField(
        max_length=255, blank=True, null=True
    )

    def __str__(self):
        return self.title

    class Meta:
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['ranking_status']),
            models.Index(fields=['visa_required']),
        ]


# ============================
# Chat Memory (Supabase-backed)
# ============================

class ChatSession(models.Model):
    MODE_CHOICES = (
        ("candidate", "Candidate"),
        ("recruiter", "Recruiter"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # optional linking (keep flexible)
    user_id = models.UUIDField(null=True, blank=True)
    candidate_slug = models.CharField(max_length=255, null=True, blank=True)

    mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_sessions"
        indexes = [
            models.Index(fields=["mode", "created_at"]),
            models.Index(fields=["candidate_slug"]),
        ]

    def __str__(self):
        return f"ChatSession({self.id}, mode={self.mode})"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ("system", "System"),
        ("user", "User"),
        ("assistant", "Assistant"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="session_id",
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
