from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ Redirect root URL to swipe_view (inside base app)
    path('', lambda request: redirect('swipe_view'), name='home'),

    # ✅ Include all routes from the base app
    path('', include('base.urls')),

    # ✅ Include your API routes
    path('api/', include('base.api.urls')),
]

# ✅ Serve media during DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
