"""One-time links must not be interchangeable.

Django's stock ``default_token_generator`` signs a password-reset link. If the
account-activation link used the same generator, an activation link lying in a
browser history or a proxy log would also reset the password for three days.
Each purpose therefore gets its own key salt, and the activation token also
depends on ``is_active`` so it dies the moment it is used.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.is_active}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
