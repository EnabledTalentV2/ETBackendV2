# candidates/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from django.shortcuts import get_object_or_404

from . import models, serializers
from .tasks import parse_resume_task


from .serializers import (
    PromptSerializer,
    PromptResponseSerializer,
    CareerCoachSerializer,
    CareerCoachResponseSerializer,
)
from .models import conversation_threads, get_resume_context, get_career_coach
import uuid

from .permissions import (
    is_employer,
    can_access_candidate_profile,
    IsOwnerOrEmployerReadOnly,
)



# =====================================================================
# CANDIDATE PROFILE VIEWSET
# =====================================================================

class CandidateViewSet(viewsets.ModelViewSet):
    permission_classes = (
    permissions.IsAuthenticated,
    IsOwnerOrEmployerReadOnly,
)

    serializer_class = serializers.CandidateProfileSerializer
    queryset = models.CandidateProfile.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "slug"

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return models.CandidateProfile.objects.none()

        # EMPLOYER: can see ALL candidates
        if is_employer(user):
            return (
                models.CandidateProfile.objects
                .all()
                .select_related("user", "organization")
                .prefetch_related("notes")
            )

        # CANDIDATE: can see ONLY self
        return (
            models.CandidateProfile.objects
            .filter(user=user)
            .select_related("user", "organization")
            .prefetch_related("notes")
        )


    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = serializers.CreateCandidateProfileSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(user=request.user)

        output = self.get_serializer(instance)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_200_OK)

    # -----------------------------------------------------------------
    # NOTES CREATION
    # -----------------------------------------------------------------

    @action(
        methods=["POST"],
        detail=True,
        url_path="create-notes",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def create_note(self, request, slug=None):
        resume_obj = self.get_object()
        serializer = serializers.CreateNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(resume=resume_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # -----------------------------------------------------------------
    # RESUME PARSING (AI SUGGESTION ONLY)
    # -----------------------------------------------------------------

    @action(methods=["POST"], detail=True, url_path="parse-resume")
    def parse_resume_data(self, request, slug=None):
        instance = self.get_object()

        if not instance.resume_file:
            return Response(
                {"error": "No resume file found for this candidate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if instance.parsing_status == "parsed" and instance.resume_data:
            return Response(
                {
                    "message": "Resume already parsed",
                    "parsing_status": instance.parsing_status,
                    "resume_data": instance.resume_data,
                },
                status=status.HTTP_200_OK,
            )

        if instance.parsing_status == "parsing":
            return Response(
                {
                    "message": "Resume parsing already in progress",
                    "parsing_status": instance.parsing_status,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            task = parse_resume_task.delay(instance.id)
            return Response(
                {
                    "message": "Resume parsing started",
                    "parsing_status": "parsing",
                    "task_id": task.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to start parsing: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # -----------------------------------------------------------------
    # PARSING STATUS CHECK
    # -----------------------------------------------------------------

    @action(methods=["GET"], detail=True, url_path="parsing-status")
    def get_parsing_status(self, request, slug=None):
        instance = self.get_object()
        return Response(
            {
                "parsing_status": instance.parsing_status,
                "has_resume_data": bool(instance.resume_data),
                "resume_file_exists": bool(instance.resume_file),
                "has_verified_data": bool(instance.skills or instance.linkedin),

            },
            status=status.HTTP_200_OK,
        )

    # -----------------------------------------------------------------
    # PROFILE VERIFICATION (AUTHORITATIVE DATA)
    # -----------------------------------------------------------------

    @action(
        methods=["POST"],
        detail=True,
        url_path="verify-profile",
        parser_classes=[JSONParser],
    )
    def verify_profile(self, request, slug=None):
        """
        Accepts USER-VERIFIED profile data.
        This is the ONLY source of truth.
        """
        instance = self.get_object()

        allowed_fields = {
            "name",
            "email",
            "linkedin",
            "skills",
            "work_experience",
        }

        verified_payload = {
            k: v for k, v in request.data.items() if k in allowed_fields
        }

        if not verified_payload:
            return Response(
                {"error": "No valid fields provided for verification"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in verified_payload.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        instance.save()


        return Response(
            {
                "message": "Profile verified successfully",
                "verified_data": verified_payload,
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# PROMPT API
# =====================================================================

class PromptAPI(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = PromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        thread_id = data.get("thread_id")

        messages = (
            conversation_threads.get(thread_id)
            if thread_id in conversation_threads
            else None
        )

        if not messages:
            thread_id = str(uuid.uuid4())

        result = get_resume_context(
            resume_slug=data["resume_slug"],
            user_query=data["input_text"],
            thread_id=thread_id,
            messages=messages,
        )

        conversation_threads[thread_id] = result["messages"]

        return Response(
            PromptResponseSerializer(
                {"output": result["response"], "thread_id": thread_id}
            ).data
        )


# =====================================================================
# NOTES VIEWSET
# =====================================================================

class NoteViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.CreateNoteSerializer
    queryset = models.Notes.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return (
            models.Notes.objects
            .filter(resume__user=self.request.user)
            .select_related("resume")
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = serializers.CreateNoteSerializer(
            instance=instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.user != instance.resume.user:
            return Response(
                {"detail": "You do not have permission to delete this note."},
                status=status.HTTP_403_FORBIDDEN,
            )

        self.perform_destroy(instance)
        return Response({"detail": "Note deleted"}, status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# CAREER COACH API
# =====================================================================

career_coach_threads = {}


class CareerCoachAPI(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = CareerCoachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        thread_id = data.get("thread_id")

        messages = (
            career_coach_threads.get(thread_id)
            if thread_id in career_coach_threads
            else None
        )

        if not messages:
            thread_id = str(uuid.uuid4())

        result = get_career_coach(
            resume_slug=data["resume_slug"],
            user_query=data["input_text"],
            thread_id=thread_id,
            messages=messages,
        )

        career_coach_threads[thread_id] = result["messages"]

        return Response(
            CareerCoachResponseSerializer(
                {"output": result["response"], "thread_id": thread_id}
            ).data
        )
