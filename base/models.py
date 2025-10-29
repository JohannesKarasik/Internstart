from django.db import models, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth.models import AbstractUser 
from django.db import models
from django.conf import settings




class SwipedJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'room')  # prevents duplicate swipe



class ListingType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
class JobListing(models.Model):
    topic = models.ForeignKey(ListingType, on_delete=models.SET_NULL, null=True)
    company_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    description = models.TextField()
    files = models.FileField(upload_to="listing_files/", blank=True, null=True)



class User(AbstractUser):
    full_name = models.CharField(max_length=200, null=True)
    email = models.EmailField(unique=True, null=False)
    bio = models.TextField(null=True, blank=True)
    occupation = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    background = models.ImageField(null=True, default="background.jpg")
    avatar = models.ImageField(null=True, default="avatar.svg")
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    currently_employed = models.BooleanField(null=True, blank=True, help_text="Is the user currently employed?")
    current_position   = models.CharField(max_length=120, null=True, blank=True)
    current_employer   = models.CharField(max_length=120, null=True, blank=True)
    total_years_experience = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Whole years")
    linkedin_url = models.URLField(blank=True, null=True)
    onboarding_shown = models.BooleanField(default=False)
    ready = models.BooleanField(default=False)


    # Resume upload
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)

    # Role choices
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('employer', 'Employer'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True)

    # Career category
    category = models.CharField(max_length=50, null=True, blank=True)

    # 🔹 Subscription choices
    SUBSCRIPTION_CHOICES = [
        ('starter', 'Starter – 50 Swipes'),
        ('pro', 'Pro – 200 Swipes'),
        ('elite', 'Elite – 500 Swipes'),
    ]
    subscription_tier = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default='starter'
    )

    total_swipes_used = models.PositiveIntegerField(default=0)

    # 🔹 Stripe integration fields
    stripe_customer_id = models.CharField(max_length=100, null=True, blank=True)
    subscription_status = models.CharField(max_length=50, null=True, blank=True)
    subscription_current_period_end = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    COUNTRY_CHOICES = [
        ('DK', '🇩🇰 Denmark'),
        ('US', '🇺🇸 United States'),
        ('UK', '🇬🇧 United Kingdom'),
        ('FRA', '🇫🇷 France'),
        ('GER', '🇩🇪 Germany'),
    ]
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, null=True, blank=True)

    desired_job_title = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="What's your desired job title?"
    )

    JOB_TYPE_CHOICES = [
        ('internship', 'Internship'),
        ('student_job', 'Student job'),
        ('full_time', 'Full-time job'),
    ]
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES, null=True, blank=True)

    # ---------------------------------------------------
    # 🔹 NEW: Education setup fields for "Finish Account"
    # ---------------------------------------------------
    UNDER_EDUCATION_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    under_education = models.CharField(
        max_length=3,
        choices=UNDER_EDUCATION_CHOICES,
        null=True,
        blank=True,
        help_text="Indicates whether the user is currently studying."
    )

    EDUCATION_LEVEL_CHOICES = [
        ('high_school', 'High School'),
        ('bachelor', 'Bachelor’s Degree'),
        ('master', 'Master’s Degree'),
        ('phd', 'PhD'),
        ('other', 'Other'),
    ]
    highest_education_level = models.CharField(
        max_length=30,
        choices=EDUCATION_LEVEL_CHOICES,
        null=True,
        blank=True,
        help_text="Highest completed education level (if not under education)."
    )

    # Field used in both cases (past or current studies)
    field_of_study = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="What did you study or what are you studying?"
    )

    current_education_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="Name of your current or last educational institution (optional)."
    )

    expected_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Expected monthly or yearly salary (depending on context)."
    )

    salary_currency = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        default="DKK",
        help_text="Currency for the expected salary, e.g. DKK, EUR, USD."
    )

    additional_skills = models.TextField(
        null=True,
        blank=True,
        help_text="List any extra skills, certifications, or tools you're proficient in."
    )



class UserGoogleCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='google_credential'
    )
    token = models.TextField()                 # access token
    refresh_token = models.TextField(null=True, blank=True)
    token_uri = models.TextField()
    client_id = models.TextField()
    client_secret = models.TextField()
    scopes = models.TextField()                # store space-separated list of scopes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Gmail credentials for {self.user.email}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, null=True)  # Additional field
    bio = models.TextField(null=True)  # Additional field

    def __str__(self):
        return self.user.username

class Topic(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name



class Room(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True)
    company_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Company logo
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)

    # Employer contact email (for applications)
    email = models.EmailField(null=True, blank=True)

    # Country field — matches user's preference
    COUNTRY_CHOICES = [
        ('DK', '🇩🇰 Denmark'),
        ('US', '🇺🇸 United States'),
        ('UK', '🇬🇧 United Kingdom'),
        ('FRA', '🇫🇷 France'),
        ('GER', '🇩🇪 Germany'),
    ]
    country = models.CharField(max_length=10, choices=COUNTRY_CHOICES, null=True, blank=True)



    # Job type field — matches user's job_type
    JOB_TYPE_CHOICES = [
        ('internship', 'Internship'),
        ('student_job', 'Student Job'),
        ('full_time', 'Full Time Job'),
    ]
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, null=True, blank=True)

    def __str__(self):
        return f"{self.job_title} at {self.company_name}"

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
    


    


class SavedJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey('Room', on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'room')



class ATSRoom(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    apply_url = models.URLField(help_text="Direct ATS application link")
    ats_type = models.CharField(
        max_length=50,
        choices=[
            ("smartrecruiters", "SmartRecruiters"),
            ("greenhouse", "Greenhouse"),
            ("lever", "Lever"),
            ("workable", "Workable"),
            ("bamboohr", "BambooHR"),
            ("workday", "Workday"),
            ("other", "Other"),
        ],
        default="other",
    )
    job_type = models.CharField(max_length=20, choices=[
        ('internship', 'Internship'),
        ('student_job', 'Student Job'),
        ('full_time', 'Full Time Job'),
    ], null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job_title} at {self.company_name}"
