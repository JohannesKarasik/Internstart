from django.contrib import admin
from .models import Connection
from .models import Message  # Import the Message model



# Register your models here.

from .models import Room, Topic, User

admin.site.register(User)
admin.site.register(Room)
admin.site.register(Topic)
admin.site.register(Connection)
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'content', 'timestamp')  # Customize fields to display
    search_fields = ('sender__full_name', 'recipient__full_name', 'content')  # Add search capabilities