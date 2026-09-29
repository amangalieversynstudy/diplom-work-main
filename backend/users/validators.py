"""Input rules for usernames and e-mail addresses that users type themselves."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

USERNAME_MAX = 150


def clean_username(value, *, exclude_pk=None):
    """A username that is safe to store and to log in with, or ValidationError.

    Usernames end up in e-mails and are one of the two login identifiers, so:
    only the characters Django allows, no ``@`` (an address-shaped username could
    shadow somebody's e-mail at login) and unique regardless of case.
    """
    User = get_user_model()
    value = str(value or "").strip()
    if not value or len(value) > USERNAME_MAX:
        raise ValidationError("Имя пользователя: от 1 до 150 символов.")
    User.username_validator(value)
    if "@" in value:
        raise ValidationError("Имя пользователя не может содержать @.")
    taken = User.objects.filter(username__iexact=value)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise ValidationError("Такое имя пользователя уже занято.")
    return value


def clean_single_email(value):
    """Exactly one syntactically valid address, or ValidationError.

    The mail backend splits recipients on commas, so a "single" address that
    contains one would be mailed to every address in the list.
    """
    value = str(value or "").strip().lower()
    if any(ch in value for ch in ",;\r\n\t "):
        raise ValidationError("Укажите один адрес электронной почты.")
    validate_email(value)
    return value
