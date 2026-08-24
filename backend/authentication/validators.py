import re

from django.core.exceptions import ValidationError


class PasswordStrengthValidator:
    """
    Lightweight strength check (sequential/repeated characters, keyboard
    walks). For full entropy scoring, swap in the `zxcvbn` package in
    production and call zxcvbn.zxcvbn(password)['score'] >= 3.
    """

    SEQUENTIAL_PATTERNS = ["0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm"]

    def validate(self, password, user=None):
        lowered = password.lower()

        if re.fullmatch(r"(.)\1+", password):
            raise ValidationError("Password cannot be a single repeated character.", code="password_repeated")

        for pattern in self.SEQUENTIAL_PATTERNS:
            for i in range(len(pattern) - 3):
                chunk = pattern[i : i + 4]
                if chunk in lowered or chunk[::-1] in lowered:
                    raise ValidationError(
                        "Password contains a predictable sequence.", code="password_sequential"
                    )

    def get_help_text(self):
        return "Your password can't be a simple repeated or sequential pattern."
