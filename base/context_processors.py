from .models import Connection  # Make sure to import the Connection model
from django.db.models import Q

def global_connections(request):
    # If the user is not authenticated, return an empty context
    if not request.user.is_authenticated:
        return {}

    # Otherwise, return the user's connections
    connections = Connection.objects.filter(Q(user=request.user) | Q(connection=request.user))
    return {'connections': connections}



