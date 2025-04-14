from django.db import models
from django.contrib.auth.models import User

class Training(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    is_paid = models.BooleanField(default=True)
    price = models.FloatField(default=0.0)
    category = models.CharField(max_length=100, blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.title

class Project(models.Model):
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    description = models.TextField()
    instructions = models.TextField()
    is_approved = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.title

class Assignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assignments')
    question = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    correct = models.CharField(max_length=255)

    def __str__(self):
        return f"Assignment for {self.project.title}"

class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    training = models.ForeignKey(Training, on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    progress = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.training.title}"

class ProjectCompletion(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('enrollment', 'project')