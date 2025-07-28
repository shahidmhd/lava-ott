from django.contrib.auth.backends import BaseBackend
from .models import User


class AdminAuthenticationBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None):
        print('--------- INSIDE -------- AdminAuthentication -------')

        try:
            user = User.objects.get(username=username)
            if user.check_password(password) is True:
                return user
            return None
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


class AppAuthenticationBackend(BaseBackend):
    def authenticate(self, request, mobile_number=None):
        print('--------- INSIDE -------- CustomAppAuthentication -------')
        try:
            user = User.objects.get(mobile_number=mobile_number)
            return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
