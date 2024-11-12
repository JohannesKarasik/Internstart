from django.db import models
from django.contrib.auth.models import AbstractUser

from django.contrib.auth.models import AbstractUser
from django.db import models

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.db import models, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings  # Import settings for custom User model reference
from django.db import models
from django.utils import timezone





class User(AbstractUser):
    full_name = models.CharField(max_length=200, null=True)
    email = models.EmailField(unique=True, null=False)
    bio = models.TextField(null=True, blank=True)
    occupation = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    background = models.ImageField(null=True, default="background.jpg")
    avatar = models.ImageField(null=True, default="avatar.svg")
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)

    USERNAME_FIELD = 'email'  # Use email for authentication
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, null=True)  # Additional field
    bio = models.TextField(null=True)  # Additional field

    def __str__(self):
        return self.user.username

class Topic(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name

class Room(models.Model):
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True)
    description = models.TextField(null=True, blank=True)
    participants = models.ManyToManyField(User, related_name='participants', blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated', '-created']

    def __str__(self):
        return self.name
    
class RoomFile(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to='room_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class ConnectionRequest(models.Model):
    sender = models.ForeignKey(User, related_name="connection_requests_sent", on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name="connection_requests_received", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username}"
    

# Connection model to store relationships between users
class Connection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="connections", on_delete=models.CASCADE)
    connection = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="connected_users", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'connection'], name='unique_connection'),
        ]

    def save(self, *args, **kwargs):
        if not Connection.objects.filter(user=self.user, connection=self.connection).exists() and \
           not Connection.objects.filter(user=self.connection, connection=self.user).exists():
            super(Connection, self).save(*args, **kwargs)
        else:
            raise IntegrityError("This connection already exists.")

    def __str__(self):
        return f"{self.user.full_name} is connected with {self.connection.full_name}"


# Message model to store the messages between users
class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="received_messages", on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.full_name} to {self.recipient.full_name}"