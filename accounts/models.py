from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_supervisor = models.BooleanField('Es supervisor', default=False)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f'{self.display_name} (@{self.username})'

