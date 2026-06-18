from django.contrib.auth.backends import BaseBackend
from .models import Users


class UsersBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        if username is None or password is None:
            return None

        try:
            user = Users.objects.get(username=username)
        except Users.DoesNotExist:
            return None

        if user.check_password(password):
            return user

        return None

    def get_user(self, user_id):
        try:
            return Users.objects.get(id=user_id)
        except Users.DoesNotExist:
            return None
