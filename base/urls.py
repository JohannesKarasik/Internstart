from django.urls import path
from . import views
from django.urls import path, include
from django.urls import path
from .forms import EmployerCompanyForm, EmployerPersonalForm
from django.urls import path, include
from django.shortcuts import redirect
from .views import swipe_static_view







urlpatterns = [
    path('', views.landing_page, name='landing_page'),   # ✅ root
    path('swipe/', views.swipe_view, name='swipe_view'),
    path('', lambda request: redirect('swipe_view'), name='home'),
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
     path("feed/", views.feed_view, name="feed"),         # feed now lives at /feed/
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
    path("swipe/jobs/", views.swipe_jobs_api, name="swipe_jobs_api"),
    path('welcome', views.landing_page, name=''),   # ✅ root
    path('import-job/', views.import_job_view, name='import_job'),




        path(
        'activate/<uidb64>/<token>/',
        views.activate_account,
        name='activate'
    ),

    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path("apply-ats/<int:room_id>/", views.apply_ats_view, name="apply_ats"),
    path("insights/", views.listings_insights_view, name="listings_insights"),
    path("run_scraper/", views.run_scraper, name="run_scraper"),
    path("process_job_with_ai_bulk/", views.process_job_with_ai_bulk, name="process_job_with_ai_bulk"),
    path("manual-import/", views.manual_import_jobs, name="manual_import_jobs"),
    path("process_manual_job/", views.process_manual_job, name="process_manual_job"),
    path("process-text/", views.process_text_page, name="process_text_page"),
    path("test-landing/", views.landing_page_test, name="landing_page_test"),
    path('blog/', views.blog_index, name='blog_index'),

    path('', views.landing_page, name='landing_page'),       # US default
    path('uk/', views.landing_page_uk, name='landing_page_uk'),
    path('dk/', views.landing_page_dk, name='landing_page_dk'),
    path('da/login/', views.login_view, name='app_login_dk'),
    path('da/register/', views.register_view, name='register_dk'),
# urls.py
    path("swipe/preview/", swipe_static_view, name="swipe_static_view"),
    # urls.py
    path("swipe/next/", views.next_card_json, name="next_card_json"),
    

















    # Home and Profile URLs


    path('profile/<int:pk>/', views.userProfile, name='user-profile'),
    
    # Room URLs
    path('room/<int:pk>/', views.room, name="room"),
    path('create-room/', views.createRoom, name="create-room"),
    path('update-room/<int:pk>/', views.updateRoom, name="update-room"),
    path('delete-room/<int:pk>/', views.deleteRoom, name='deleteRoom'),
    path('terms/', views.terms_conditions, name='terms_conditions'),
    path("cancel-subscription/", views.cancel_subscription, name="cancel_subscription"),
    path("revoke-google-access/", views.revoke_google_access, name="revoke_google_access"),




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
    

    #blog posts####################################
    path('blog/how-to-write-resume-for-internship/', views.blog_resume_internship, name='blog_resume_internship'),

    path(
        'blog/when-to-apply-for-summer-internships/',
        views.blog_when_to_apply_for_summer_internships,
        name='blog_when_to_apply_for_summer_internships',
    ),

    path(
        'blog/cover-letter-for-internship/',
        views.cover_letter_for_internship,
        name='blog_cover_letter_for_internship',
    ),

        path(
        'blog/how_to_find_internships_with_no_experience/',
        views.how_to_find_internships_with_no_experience,
        name='how_to_find_internships_with_no_experience',
    ),

        path(
        'blog/how_to_get_a_remote_internship/',
        views.how_to_get_a_remote_internship,
        name='how_to_get_a_remote_internship',
    ),


        path(
        'blog/skills_for_internship_resume/',
        views.skills_for_internship_resume,
        name='skills_for_internship_resume',
    ),


        path('blog/top-25-best-college-student-jobs/', views.college_student_jobs, name='college_student_jobs'),

        path('blog/top_20_nursing_student_jobs/', views.top_20_nursing_student_jobs, name='top_20_nursing_student_jobs'),

        path('blog/how_to_get_into_finance/', views.how_to_get_into_finance, name='how_to_get_into_finance'),

        path('blog/how_to_get_into_finance_with_no_degree/', views.how_to_get_into_finance_with_no_degree, name='how_to_get_into_finance_with_no_degree'),

        path('blog/how-to-get-a-job-fast/', views.how_to_get_a_job_fast, name='how-to-get-a-job-fast'),






    ##############################################

    path("robots.txt", views.robots_txt, name="robots_txt"),


    # Health Check URL
    path('health/', views.health_check, name='health_check'),
]
