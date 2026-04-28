from datetime import date

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


# Custom user model needed (enforce uniqueness of email)
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("role", "member")
        extra_fields.setdefault("salutation", "Mr.")
        extra_fields.setdefault("first_mid_name", "")
        extra_fields.setdefault("last_name", "")
        extra_fields.setdefault("country_code", "+62")
        extra_fields.setdefault("mobile_number", "")
        extra_fields.setdefault("tanggal_lahir", date(2000, 1, 1))
        extra_fields.setdefault("kewarganegaraan", "Indonesia")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "staff")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Meta:
        managed = False
        db_table = "main_user"

    username = None  # remove username field

    ROLE_CHOICES = (
        ("member", "Member"),
        ("staff", "Staff"),
    )
    SALUTATION_CHOICES = (
        ("Mr.", "Mr."),
        ("Ms.", "Ms."),
        ("Mrs.", "Mrs."),
        ("Dr.", "Dr."),
    )
    COUNTRY_CODE = (("+62", "+62"), ("+60", "+60"), ("+65", "+65"))
    COUNTRY_CHOICES = (
        ("Indonesia", "ID - Indonesia"),
        ("Malaysia", "MY - Malaysia"),
        ("Singapura", "SG - Singapura"),
    )

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    salutation = models.CharField(max_length=10, choices=SALUTATION_CHOICES)
    first_mid_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=5, choices=COUNTRY_CODE)
    mobile_number = models.CharField(max_length=20)
    tanggal_lahir = models.DateField()
    kewarganegaraan = models.CharField(max_length=50, choices=COUNTRY_CHOICES)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # since email is used instead of username

    objects = UserManager()

    def __str__(self):
        return self.email
