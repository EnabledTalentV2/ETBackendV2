from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import validate_image_file_extension
from .managers import CustomUserManager
from datetime import timedelta
import random


class User(AbstractUser):
    username = None
    email = models.EmailField(("email address"), unique=True)
    newsletter = models.BooleanField(default=True)
    last_online = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def clean(self):
        super().clean()
        self.email = self.email.lower()

    def save(self, *args, **kwargs):
        is_created = self._state.adding
        self.clean()
        super().save(*args, **kwargs)

        if is_created:
            Profile.objects.create(user=self)

    def __str__(self):
        return self.email


# =====================================================================
# PROFILE (Uses Supabase Storage URLs, NOT Django ImageFields)
# =====================================================================

def generate_referral_code():
    return "".join([str(random.randint(0, 9)) for _ in range(6)])


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # 🔥 Supabase-ready: This now stores a public URL instead of an image file.
    avatar_url = models.URLField(max_length=500, null=True, blank=True)

    referral_code = models.CharField(
        max_length=6, unique=True, default=generate_referral_code, blank=True
    )
    total_referrals = models.IntegerField(default=0)

    def create_random(self):
        return "".join([str(random.randint(0, 9)) for _ in range(6)])

    def save(self, *args, **kwargs):
        if not self.referral_code:
            code = self.create_random()

            while Profile.objects.filter(referral_code=code).exists():
                code = self.create_random()

            self.referral_code = code

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.user)


# =====================================================================
# FEEDBACK MODEL (attachment → Supabase URL)
# =====================================================================

URGENCYY = tuple((i, i) for i in range(1, 10))


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    urgency = models.IntegerField(choices=URGENCYY)
    subject = models.CharField(max_length=30)
    message = models.TextField()
    emoji = models.CharField(max_length=50, blank=True, null=True)

    # 🔥 Supabase URL instead of ImageField
    attachment_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.user.email


# =====================================================================
# EMAIL VERIFICATION TOKEN
# =====================================================================

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

            while EmailVerificationToken.objects.filter(code=self.code).exists():
                self.code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.code}"

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)
