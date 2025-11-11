from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import BlogPost

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "published_at", "updated_at", "display_author")
    list_filter = ("status", "published_at", "updated_at")
    search_fields = ("title", "excerpt", "content", "author_name")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Content", {"fields": ("title", "slug", "excerpt", "content")}),
        ("Author", {"fields": ("author", "author_name")}),
        ("Images", {"fields": ("header_image", "og_image")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "canonical_url")}),
        ("Publishing", {"fields": ("status", "published_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
