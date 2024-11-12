from django.urls import path
from . import views


urlpatterns = [
    path('', views.landing_page, name='landing_page'),  # Root URL for the landing page
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('register/', views.registerPage, name="register"),
    path('home/', views.home, name="home"),  # Changed to a non-root URL for home
    path('room/<str:pk>/', views.room, name="room"),
    path('profile/<str:pk>/', views.userProfile, name="user-profile"),
    path('create-room/', views.createRoom, name="create-room"),
    path('update-room/<str:pk>/', views.updateRoom, name="update-room"),
    path('delete-room/<int:pk>/', views.deleteRoom, name='deleteRoom'),  # Correct URL pattern for deleteRoom
    path('update-user/', views.updateUser, name="update-user"),
    path('topics/', views.topicsPage, name="topics"),
    path('edit-room/<int:pk>/', views.updateRoom, name='updateRoom'),
    path('send-connection-request/<int:user_id>/', views.send_connection_request, name='send_connection_request'),
    path('accept-connection-request/<int:request_id>/', views.accept_connection_request, name='accept_connection_request'),
    path('connections/', views.view_connections, name='view_connections'),
    path('connections/<int:pk>/', views.view_connections, name='view_connections'),
    path('profile/<int:pk>/', views.userProfile, name='user-profile'),
    path('send_message/', views.send_message, name='send_message'),
    path('messages/<int:user_id>/', views.message_room, name='message_room'),
    path('load_messages_fragment/<int:user_id>/', views.load_messages_fragment, name='load_messages_fragment'),
   


]
 







