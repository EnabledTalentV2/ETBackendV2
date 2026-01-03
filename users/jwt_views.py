from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from .jwt_serializers import EmailTokenObtainPairSerializer


class EmailTokenObtainPairView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = EmailTokenObtainPairSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
