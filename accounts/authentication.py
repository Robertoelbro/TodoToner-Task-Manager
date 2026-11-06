from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import User


def find_login_user(identifier):
    """Un identificador ambiguo nunca debe elegir una cuenta arbitrariamente."""
    if not identifier:
        return None
    users = list(User.objects.filter(
        Q(username=identifier) | Q(allow_email_login=True, email__iexact=identifier)
    )[:2])
    return users[0] if len(users) == 1 else None


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user = find_login_user(username.strip())
        if user is None:
            # Mantener el coste de verificación también cuando la cuenta no existe.
            User().set_password(password)
            return None
        if (user.check_password(password) and self.user_can_authenticate(user)
                and not user.deletion_due_at and not user.deleted_at):
            return user
        return None
