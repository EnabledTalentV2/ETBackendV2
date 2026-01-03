from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Skills, JobPost


admin.site.register(Skills)
admin.site.register(JobPost)