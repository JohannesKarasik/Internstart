from django.contrib import admin
from .models import Connection
from .models import Message  # Import the Message model
from .models import ATSRoom
from .models import RoomAttribute



# Register your models here.

from .models import Room, Topic, User

admin.site.register(User)
admin.site.register(Room)
admin.site.register(Topic)
admin.site.register(Connection)
admin.site.register(RoomAttribute)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'content', 'timestamp')  # Customize fields to display
    search_fields = ('sender__full_name', 'recipient__full_name', 'content')  # Add search capabilities


@admin.register(ATSRoom)
class ATSRoomAdmin(admin.ModelAdmin):
    list_display = ("company_name", "job_title", "ats_type", "apply_url", "created_at")
    search_fields = ("company_name", "job_title", "ats_type")