from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    bio = models.TextField()
    location = models.CharField(max_length=100)
    certifications = models.FileField(
        upload_to="certifications/", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills",
    )

    def __str__(self):
        return self.name


class UserSkill(models.Model):
    SKILL_ROLE = (
        ("offer", "Can Offer"),
        ("seek", "Looking For"),
    )

    PROFICIENCY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
        ("expert", "Expert"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=SKILL_ROLE, default="offer")
    proficiency = models.CharField(
        max_length=20, choices=PROFICIENCY_CHOICES, default="beginner"
    )
    experience_years = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "skill", "role")
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["proficiency"]),
            models.Index(fields=["user", "role"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.skill.name} ({self.role})"


class Exchange(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("dispute", "Dispute"),
        ("cancelled", "Cancelled"),
    ]

    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exchanges_as_user1",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exchanges_as_user2",
    )

    skill1 = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, related_name="offered_exchanges"
    )
    skill2 = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, related_name="received_exchanges"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    user1_completed = models.BooleanField(default=False, help_text="User1 marked their part as complete")
    user2_completed = models.BooleanField(default=False, help_text="User2 marked their part as complete")
    user1_completed_date = models.DateTimeField(null=True, blank=True)
    user2_completed_date = models.DateTimeField(null=True, blank=True)
    admin_approved = models.BooleanField(default=False, help_text="Admin verified both users completed the exchange")
    admin_approved_date = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, help_text="Admin notes about this exchange")

    def __str__(self):
        return f"{self.user1.username} ↔ {self.user2.username} ({self.skill1} ↔ {self.skill2})"
    
    def both_users_completed(self):
        return self.user1_completed and self.user2_completed
    
    def completion_status(self):
        if self.admin_approved:
            return "Admin Approved"
        elif self.both_users_completed():
            return "Awaiting Admin Approval"
        elif self.user1_completed or self.user2_completed:
            return "Partially Complete"
        else:
            return "In Progress"

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Exchange"
        verbose_name_plural = "Exchanges"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user1", "status"]),
            models.Index(fields=["user2", "status"]),
            models.Index(fields=["-start_date"]),
        ]


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["is_read"]),
            models.Index(fields=["receiver", "is_read"]),
            models.Index(fields=["sender", "receiver"]),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.content[:30]}"
