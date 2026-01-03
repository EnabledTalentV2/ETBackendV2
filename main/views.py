from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from . import models, serializers
from .serializers import AgentQuerySerializer, AgentResponseSerializer
from .tasks import rank_candidates_task
from main.agent import query_candidates


class JobPostViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD for Job Posts + Candidate Ranking Actions
    """
    permission_classes = (permissions.IsAuthenticated,)
    queryset = models.JobPost.objects.all()
    serializer_class = serializers.JobPostSerializer

    # ------------------------------------------------------------------
    # LIST JOB POSTS (Only from user's organization)
    # ------------------------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        org = user.organization_set.first()
        if not org:
            return models.JobPost.objects.none()

        return (
            models.JobPost.objects.filter(organization=org)
            .select_related("user", "organization")
            .prefetch_related("skills")
        )

    # ------------------------------------------------------------------
    # CREATE JOB POST
    # ------------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        user = request.user
        org = user.organization_set.first()

        if not org:
            return Response(
                {"detail": "User is not part of any organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = serializers.JobPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(user=user, organization=org)

        # Return full job post serializer
        out = serializers.JobPostSerializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # UPDATE JOB POST
    # ------------------------------------------------------------------
    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = serializers.JobPostCreateSerializer(
            instance=instance,
            data=request.data,
            partial=(request.method == "PATCH")
        )
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        return Response(
            serializers.JobPostSerializer(instance).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # DELETE JOB POST
    # ------------------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # ACTION: Trigger Candidate Ranking
    # ------------------------------------------------------------------
    @action(methods=["POST"], detail=True, url_path="rank-candidates")
    def rank_candidates(self, request, pk=None):
        job = self.get_object()

        # Already ranked
        if job.ranking_status == "ranked" and job.candidate_ranking_data:
            return Response(
                {
                    "message": "Candidates already ranked",
                    "ranking_status": job.ranking_status,
                    "data": job.candidate_ranking_data,
                },
                status=status.HTTP_200_OK,
            )

        # In progress
        if job.ranking_status == "ranking":
            return Response(
                {
                    "message": "Ranking already in progress",
                    "ranking_status": job.ranking_status,
                    "task_id": job.ranking_task_id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            # Assign status BEFORE dispatch
            job.ranking_status = "ranking"
            job.save(update_fields=["ranking_status"])

            task = rank_candidates_task.delay(job.id)

            job.ranking_task_id = task.id
            job.save(update_fields=["ranking_task_id"])

            return Response(
                {
                    "message": "Candidate ranking started",
                    "ranking_status": "ranking",
                    "task_id": task.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            return Response(
                {"error": f"Error starting ranking: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------
    # ACTION: Retrieve Ranking Data
    # ------------------------------------------------------------------
    @action(methods=["GET"], detail=True, url_path="ranking-data")
    def get_ranking_data(self, request, pk=None):
        job = self.get_object()

        cache_key = f"job_ranking_data_{job.id}"
        cached = cache.get(cache_key)

        if cached:
            return Response(cached, status=status.HTTP_200_OK)

        if not job.candidate_ranking_data:
            return Response(
                {"detail": "No ranking data available."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cache.set(cache_key, job.candidate_ranking_data, 3600)
        return Response(job.candidate_ranking_data, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# AGENT API — Search Candidates (LLM Based)
# ----------------------------------------------------------------------

class AgentAPI(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = AgentQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]

        results = query_candidates(query)

        response = AgentResponseSerializer({"results": results})
        return Response(response.data)
