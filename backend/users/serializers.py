from game.models import ClassRole
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    class_role = serializers.PrimaryKeyRelatedField(
        queryset=ClassRole.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = ["xp", "level", "bio", "class_role"]
        read_only_fields = ("xp", "level")
        ref_name = "UsersProfileSerializer"

    def validate_class_role(self, value):
        # класс выбирается один раз — не разрешаем смену через PATCH
        profile = getattr(self, "instance", None)
        if profile and profile.class_role_id:
            if value is None or value.id != profile.class_role_id:
                raise serializers.ValidationError(
                    "Class role can be selected only once for this profile."
                )
        return value


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
