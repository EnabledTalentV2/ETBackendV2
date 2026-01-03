# organization/models.py

from django.db import models, transaction
from django.utils.crypto import get_random_string
from users.models import User


INDUSTRIES = (
    (1, "IT SERVICES"),
    (2, "Product Based"),
    (3, "Finance"),
    (4, "Sport"),
    (5, "Healthcare"),
    (6, "Automobile"),
    (7, "Non-Profit"),
    (8, "Public-Sector"),
    (9, "Retail"),
    (10, "Hospitality"),
    (11, "Business"),
    (12, "Others"),
)

COMPANY_SIZING = (
    (1, "1-10"),
    (2, "10-100"),
    (3, "100-500"),
    (4, "500-1000"),
    (5, "1000+"),
)


# =====================================================================
# ORGANIZATION MODEL — SUPABASE READY
# =====================================================================

class Organization(models.Model):
    root_user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="organization_root_user",
    )

    users = models.ManyToManyField(
        User,
        related_name="organizations",   # ✔ fixes reverse lookup
        blank=True
    )

    name = models.CharField(max_length=100)
    industry = models.IntegerField(choices=INDUSTRIES)
    headquarter_location = models.CharField(max_length=100)
    about = models.TextField()
    employee_size = models.IntegerField(choices=COMPANY_SIZING)

    # public/org URLs
    url = models.URLField(unique=True, blank=True, null=True)
    linkedin_url = models.URLField(unique=True, blank=True, null=True)

    # ✔ Supabase stored URL, not ImageField
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["industry"]),
            models.Index(fields=["employee_size"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_being_created = self._state.adding
        super().save(*args, **kwargs)

        if is_being_created:
            def add_member():
                self.users.add(self.root_user)

            transaction.on_commit(add_member)


# =====================================================================
# ORGANIZATION INVITE MODEL
# =====================================================================

def create_organization_invite():
    return get_random_string(10)


class OrganizationInvite(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    invite_code = models.CharField(max_length=20, default=create_organization_invite)
    email = models.EmailField()
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["invite_code"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"Invite ({self.email}) → {self.organization.name}"
