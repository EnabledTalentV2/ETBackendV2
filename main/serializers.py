from rest_framework import serializers
from . import models
from users.serializers import UserSerializer
from organization.serializers import OrganizationSerializer


# ---------------------------------------------------------------------
# SKILL SERIALIZER
# ---------------------------------------------------------------------

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Skills
        fields = ["id", "name"]


# ---------------------------------------------------------------------
# JOB POST CREATE / UPDATE SERIALIZER
# ---------------------------------------------------------------------

class JobPostCreateSerializer(serializers.ModelSerializer):
    # Incoming format → ["Python", "Django"] OR [{"name": "Python"}, ...]
    skills = serializers.ListField(write_only=True)

    class Meta:
        model = models.JobPost
        fields = [
            "title",
            "job_desc",
            "workplace_type",
            "location",
            "job_type",
            "skills",
            "estimated_salary",
            "visa_required",
        ]

    def create(self, validated_data):
        """Create JobPost with skill linking."""
        skills_data = validated_data.pop("skills", [])

        # user & organization passed in save(user=..., organization=...)
        user = validated_data.pop("user")
        organization = validated_data.pop("organization")

        job_post = models.JobPost.objects.create(
            user=user,
            organization=organization,
            **validated_data,
        )

        # Add skills
        for item in skills_data:
            if isinstance(item, dict) and "name" in item:
                name = item["name"]
            else:
                name = item

            skill, _ = models.Skills.objects.get_or_create(name=name)
            job_post.skills.add(skill)

        return job_post

    def update(self, instance, validated_data):
        """Update job post incl. skills."""
        skills_data = validated_data.pop("skills", None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update skills only if provided
        if skills_data is not None:
            new_skill_objs = []
            for item in skills_data:
                if isinstance(item, dict) and "name" in item:
                    name = item["name"]
                else:
                    name = item
                skill, _ = models.Skills.objects.get_or_create(name=name)
                new_skill_objs.append(skill)

            instance.skills.set(new_skill_objs)

        instance.save()
        return instance


# ---------------------------------------------------------------------
# JOB POST READ SERIALIZER
# ---------------------------------------------------------------------

class JobPostSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    organization = OrganizationSerializer()
    skills = SkillSerializer(many=True)

    class Meta:
        model = models.JobPost
        fields = [
            "id",
            "user",
            "organization",
            "title",
            "job_desc",
            "workplace_type",
            "location",
            "job_type",
            "skills",
            "estimated_salary",
            "visa_required",
            "candidate_ranking_data",
            "ranking_status",
            "ranking_task_id",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------
# AGENT / RANKING SERIALIZERS
# ---------------------------------------------------------------------

class AgentQuerySerializer(serializers.Serializer):
    query = serializers.CharField(help_text="Recruiter's query for ranking candidates")


class AgentResponseSerializer(serializers.Serializer):
    results = serializers.JSONField(help_text="Ranking results returned by the AI engine")
