from django.urls import path
from . import views
from django.urls import path, include
from django.urls import path
from .forms import EmployerCompanyForm, EmployerPersonalForm
from django.urls import path, include




urlpatterns = [
    path('', views.landing_page, name='landing_page'),  # Root URL for the landing page
    path('login/', views.loginPage, name="app_login"),
    path('logout/', views.logoutUser, name="app_logout"),
    path('register/', views.registerPage, name="register"),
    path('send-test-email/', views.send_test_email, name='send_test_email'),
    path('start-gmail-auth/', views.start_gmail_auth, name='start_gmail_auth'),
    path('gmail/callback/', views.gmail_callback, name='gmail_callback'),
    path('resume/<int:user_id>/', views.view_resume, name='view_resume'),
    path('generate-coverletter/', views.generate_coverletter, name='generate_coverletter'),
    path('send-application/', views.send_application, name='send_application'),
    path('company/<int:pk>/', views.company_profile, name='company-profile'),
    path("", views.feed_view, name="feed"),        # default feed mode
    path("swipe/", views.swipe_view, name="swipe_view"), # swipe mode
    path('apply-swipe-job/', views.apply_swipe_job, name='apply_swipe_job'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('start-gmail-auth/', views.start_gmail_auth, name='start_gmail_auth'),
    path("billing/", include("billing.urls")),
    path('billing/success/', views.billing_success, name='billing_success'),
    path('billing/cancel/', views.billing_cancel, name='billing_cancel'),
    path('save-job/', views.save_job, name='save_job'),
    path('saved-jobs/json/', views.saved_jobs_json, name='saved_jobs_json'),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("billing/checkout/<str:tier>/", views.create_checkout_session, name="create_checkout_session"),
    path("billing/success/", views.billing_success, name="billing_success"),
    path("billing/cancel/", views.billing_cancel, name="billing_cancel"),

        path(
        'activate/<uidb64>/<token>/',
        views.activate_account,
        name='activate'
    ),

    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),








    # Home and Profile URLs

    path('swipe/', views.swipe_view, name='home'),   # alias "home" to swipe_view

    path('profile/<int:pk>/', views.userProfile, name='user-profile'),
    
    # Room URLs
    path('room/<int:pk>/', views.room, name="room"),
    path('create-room/', views.createRoom, name="create-room"),
    path('update-room/<int:pk>/', views.updateRoom, name="update-room"),
    path('delete-room/<int:pk>/', views.deleteRoom, name='deleteRoom'),
    path('terms/', views.terms_conditions, name='terms_conditions'),


    # User and Topics
    path('update-user/', views.updateUser, name="update-user"),
    path('topics/', views.topicsPage, name="topics"),
    path('debug/set-tier/', views.debug_set_tier, name='debug_set_tier'),

    # Connections URLs
    path('send-connection-request/<int:user_id>/', views.send_connection_request, name='send_connection_request'),
    path('accept-connection-request/<int:request_id>/', views.accept_connection_request, name='accept_connection_request'),
    path('connections/<int:user_id>/', views.view_connections, name='view_connections'),    
    path('quota/', views.get_quota, name='get_quota'),

    
    # Messaging URLs
    path('send_message/', views.send_message, name='send_message'),
    path('messages/<int:user_id>/', views.message_room, name='message_room'),
    path('load_messages_fragment/<int:user_id>/', views.load_messages_fragment, name='load_messages_fragment'),
    
    # Health Check URL
    path('health/', views.health_check, name='health_check'),
]
