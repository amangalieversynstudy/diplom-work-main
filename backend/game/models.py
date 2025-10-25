from django.db import models

class ClassRole(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.title

class Mission(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='missions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    xp_reward = models.IntegerField(default=10)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class Progress(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='progress')
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
