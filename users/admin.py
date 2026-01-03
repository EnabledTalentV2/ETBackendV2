from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User,Profile, EmailVerificationToken, Feedback


admin.site.register(User)
admin.site.register(Profile)
admin.site.register(EmailVerificationToken)
admin.site.register(Feedback)