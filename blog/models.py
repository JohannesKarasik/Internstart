from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

User = get_user_model()

class BlogPost(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
    )

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, help_text="Auto-generated from title; edit if needed.")
    excerpt = models.TextField(blank=True, help_text="Short description used in cards and meta.")
    content = models.TextField(blank=True)

    # Author can be optional FK (use your app’s users if you like)
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    author_name = models.CharField(max_length=120, blank=True, help_text="Fallback author name if no user.")

    # Images
    header_image = models.ImageField(upload_to="blog/", blank=True, null=True, help_text="Hero / card image")
    og_image = models.ImageField(upload_to="blog/og/", blank=True, null=True)

    # SEO / meta
    canonical_url = models.URLField(blank=True)
    meta_title = models.CharField(max_length=70, blank=True, help_text="Recommended ≤ 60–65 chars.")
    meta_description = models.CharField(max_length=160, blank=True, help_text="Recommended ≤ 155–160 chars.")

    # Publishing
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog_detail", kwargs={"slug": self.slug})

    @property
    def display_author(self):
        if self.author and (self.author.get_full_name() or self.author.username):
            return self.author.get_full_name() or self.author.username
        return self.author_name or "Internstart Editorial"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:180]
        super().save(*args, **kwargs)
