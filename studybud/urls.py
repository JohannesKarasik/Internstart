from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.shortcuts import redirect
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap, BlogSitemap

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('swipe_view')
    return redirect('landing_page')

sitemaps = {
    "static": StaticViewSitemap,
    "blog": BlogSitemap,
}


urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ Include all routes from the base app (handles "/" correctly)
    path('', include('base.urls')),

    path('api/', include('base.api.urls')),

        path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),



]

# ✅ Serve media during DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
