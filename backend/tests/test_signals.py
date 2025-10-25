import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_profile_created_on_user_creation():
    u = User.objects.create_user(username='signal_user', password='pw')
    assert hasattr(u, 'profile')
    assert u.profile.xp == 0
    assert u.profile.level == 1
