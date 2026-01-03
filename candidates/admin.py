from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import CandidateProfile, Notes

admin.site.register(CandidateProfile)
admin.site.register(Notes)