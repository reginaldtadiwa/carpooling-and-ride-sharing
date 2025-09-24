# accounts/api.py
from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer, UserProfileSerializer

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user