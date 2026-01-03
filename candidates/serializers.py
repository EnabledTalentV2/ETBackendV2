from rest_framework import serializers
from . import models
from users.serializers import UserSerializer
from organization.serializers import OrganizationSerializer
from backend.supabase_storage import SupabaseStorageService


# =====================================================================
# CREATE / UPDATE CANDIDATE PROFILE
# =====================================================================

class CreateCandidateProfileSerializer(serializers.ModelSerializer):
    resume_file = serializers.FileField(required=False)
    video_pitch = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = models.CandidateProfile
        fields = [
            "resume_file",
            "willing_to_relocate",
            "employment_type_preferences",
            "work_mode_preferences",
            "has_workvisa",
            "expected_salary_range",
            "video_pitch",
            "is_available",
            "disability_categories",
            "accommodation_needs",
            "workplace_accommodations",
        ]

    def create(self, validated_data):
        resume = validated_data.pop("resume_file", None)
        video = validated_data.pop("video_pitch", None)

        user = validated_data.pop("user")

        candidate = models.CandidateProfile.objects.create(
            user=user,
            **validated_data,
        )

        # Upload resume to Supabase
        if resume:
            url, _ = SupabaseStorageService.upload_file(
                resume,
                folder="candidate-resumes",
            )
            candidate.resume_file = url
            candidate.save(update_fields=["resume_file"])

        # Upload video to Supabase
        if video:
            url, _ = SupabaseStorageService.upload_file(
                video,
                folder="candidate-video-pitches",
            )
            candidate.video_pitch = url
            candidate.save(update_fields=["video_pitch"])

        return candidate

    def update(self, instance, validated_data):
        resume = validated_data.pop("resume_file", None)
        video = validated_data.pop("video_pitch", None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace resume
        if resume:
            url, _ = SupabaseStorageService.upload_file(
                resume,
                folder="candidate-resumes",
            )
            instance.resume_file = url
            instance.save(update_fields=["resume_file"])

        # Replace video
        if video:
            url, _ = SupabaseStorageService.upload_file(
                video,
                folder="candidate-video-pitches",
            )
            instance.video_pitch = url
            instance.save(update_fields=["video_pitch"])

        return instance


# =====================================================================
# NOTE SERIALIZER (READ)
# =====================================================================

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notes
        fields = [
            "identifier",
            "note",
            "note_file",
            "section",
            "selected_text",
            "context",
            "id",
            "created_at",
        ]


# =====================================================================
# CANDIDATE PROFILE SERIALIZER (READ)
# =====================================================================

class CandidateProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    organization = OrganizationSerializer()
    get_all_notes = NoteSerializer(many=True)

    class Meta:
        model = models.CandidateProfile
        fields = [
            "user",
            "organization",
            "id",
            "slug",
            "resume_file",
            "resume_data",
            "willing_to_relocate",
            "employment_type_preferences",
            "work_mode_preferences",
            "has_workvisa",
            "expected_salary_range",
            "video_pitch",
            "is_available",
            "get_all_notes",
            "disability_categories",
            "accommodation_needs",
            "workplace_accommodations",
            "created_at",
            "updated_at",
        ]


# =====================================================================
# NOTE CREATION / UPDATE
# =====================================================================

class CreateNoteSerializer(serializers.ModelSerializer):
    note_file = serializers.FileField(required=False)

    class Meta:
        model = models.Notes
        fields = [
            "identifier",
            "note",
            "section",
            "selected_text",
            "context",
            "note_file",
        ]

    def create(self, validated_data):
        file = validated_data.pop("note_file", None)
        resume = validated_data.pop("resume")

        note = models.Notes.objects.create(
            resume=resume,
            **validated_data,
        )

        if file:
            url, _ = SupabaseStorageService.upload_file(
                file,
                folder="candidate-notes",
            )
            note.note_file = url
            note.save(update_fields=["note_file"])

        return note

    def update(self, instance, validated_data):
        file = validated_data.pop("note_file", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if file:
            url, _ = SupabaseStorageService.upload_file(
                file,
                folder="candidate-notes",
            )
            instance.note_file = url
            instance.save(update_fields=["note_file"])

        return instance


# =====================================================================
# PROMPT / CAREER COACH
# =====================================================================

class PromptSerializer(serializers.Serializer):
    input_text = serializers.CharField()
    resume_slug = serializers.CharField()
    thread_id = serializers.CharField(required=False, allow_null=True)


class PromptResponseSerializer(serializers.Serializer):
    output = serializers.CharField()
    thread_id = serializers.CharField()


class CareerCoachSerializer(serializers.Serializer):
    input_text = serializers.CharField()
    resume_slug = serializers.CharField()
    thread_id = serializers.CharField(required=False, allow_null=True)


class CareerCoachResponseSerializer(serializers.Serializer):
    output = serializers.CharField()
    thread_id = serializers.CharField()
