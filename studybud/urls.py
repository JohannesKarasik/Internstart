from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect




urlpatterns = [
    path('admin/', admin.site.urls),
        path('', lambda request: redirect('swipe_view'), name='home'),  # 👈 redirect homepage to /swipe/
    path('api/', include('base.api.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
