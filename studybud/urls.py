from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.shortcuts import redirect

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('swipe_view')
    return redirect('landing_page')


urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ Only redirect logged-in users to swipe
    path('', root_redirect, name='home'),

    # ✅ Include all routes from the base app
    path('', include('base.urls')),

    path('api/', include('base.api.urls')),
]

# ✅ Serve media during DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
