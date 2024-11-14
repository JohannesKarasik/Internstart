from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from .models import Room, Topic, User
from .forms import RoomForm, UserForm, MyUserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.forms import modelformset_factory
from .models import Room, RoomFile, Topic
from .forms import RoomForm, RoomFileFormSet
from django.contrib.auth.decorators import login_required
import mimetypes
from django import template
from django.shortcuts import render, get_object_or_404
from .models import ConnectionRequest, Connection
from django.db import IntegrityError
from base.models import Connection
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import User, Connection
from django.db.models import Q
from.models import Connection
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Connection, Message, User  # Import custom User model
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render
from .models import Connection, Message
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from .models import Connection
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok"})





register = template.Library()






@register.filter
def is_image(file_path):
    mime = mimetypes.guess_type(file_path)[0]
    return mime and mime.startswith('image')


def landing_page(request):
    return render(request, 'base/landing_page.html')



def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Username OR password does not exit')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)


def logoutUser(request):
    logout(request)
    return redirect('home')


def registerPage(request):
    form = MyUserCreationForm()

    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.full_name = user.full_name.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'An error occurred during registration')

    return render(request, 'base/login_register.html', {'form': form})




@login_required(login_url='login')
def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''

    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |

        Q(description__icontains=q)
    )

    topics = Topic.objects.all()[0:5]
    room_count = rooms.count()
    context = {'rooms': rooms, 'topics': topics,
               'room_count': room_count}
    return render(request, 'base/home.html', context)

@login_required(login_url='login')
def room(request, pk):
    room = Room.objects.get(id=pk)
    room_messages = room.message_set.all()
    participants = room.participants.all()

    if request.user not in participants:
        room.participants.add(request.user)

    context = {
        'room': room,
        'room_messages': room_messages,
        'participants': participants
    }

    return render(request, 'base/room.html', context)

@login_required
def userProfile(request, pk):
    user = get_object_or_404(User, id=pk)
    rooms = Room.objects.filter(host=user)  # Fetch rooms created by this user

    # Fetch the actual sent request (if it exists)
    sent_request = ConnectionRequest.objects.filter(sender=request.user, receiver=user).first()
    # Fetch the actual received request (if it exists)
    received_request = ConnectionRequest.objects.filter(sender=user, receiver=request.user).first()

    context = {
        'user': user,
        'rooms': rooms,  # Pass rooms to the template
        'sent_request': sent_request,  # Pass the actual request object
        'received_request': received_request,  # Pass the actual request object
    }
    return render(request, 'base/profile.html', context)

@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()  # Fetch all predefined topics

    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)

        if form.is_valid():
            selected_topic_id = request.POST.get('topic')  # Get the selected topic ID from the POST data
            topic = Topic.objects.get(id=selected_topic_id)  # Fetch the selected topic from the database

            room = form.save(commit=False)
            room.host = request.user
            room.topic = topic  # Assign the selected topic
            room.save()

            # Handle multiple file uploads
            files = request.FILES.getlist('files')
            for file in files:
                RoomFile.objects.create(room=room, file=file)

            messages.success(request, 'Room created successfully!')
            return redirect('home')
        else:
            messages.error(request, 'There was an error creating the room. Please check the form for errors.')

    context = {
        'form': form,
        'topics': topics,  # Pass the predefined topics to the template
    }
    return render(request, 'base/room_form.html', context)


@login_required(login_url='login')
def updateRoom(request, pk):
    room = get_object_or_404(Room, id=pk)
    form = RoomForm(instance=room)  # Prepopulate the form with the current room details
    topics = Topic.objects.all()  # Assuming you want to show all topics

    # Ensure only the room host can edit the room
    if request.user != room.host:
        return HttpResponse('You are not allowed here!!')

    if request.method == 'POST':
        # Handle form data and file uploads (if applicable)
        topic_name = request.POST.get('topic')  # Get the topic name from the form
        topic, created = Topic.objects.get_or_create(name=topic_name)  # Create or get the topic

        # Update the room fields with the new data
        room.topic = topic
        room.description = request.POST.get('description')
        room.save()

        # Handle multiple files (if your form includes file upload functionality)
        files = request.FILES.getlist('files')
        for file in files:
            RoomFile.objects.create(room=room, file=file)  # Save uploaded files

        # Redirect to the home page after successful update
        return redirect('home')

    # Pass the form and topics to the template for rendering
    context = {'form': form, 'topics': topics, 'room': room}
    return render(request, 'base/room_form.html', context)


@login_required(login_url='login')
def deleteRoom(request, pk):
    room = Room.objects.get(id=pk)

    if request.user != room.host:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': room})




@login_required(login_url='login')
def updateUser(request):
    user = request.user
    form = UserForm(instance=user)

    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user-profile', pk=user.id)

    return render(request, 'base/update-user.html', {'form': form})

@login_required(login_url='login')
def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains=q)
    return render(request, 'base/topics.html', {'topics': topics})

@login_required(login_url='login')
def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''

    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |

        Q(description__icontains=q)
    )

    topics = Topic.objects.all()[0:5]
    room_count = rooms.count()


    user_profile = request.user  # Get the logged-in user's profile information

    context = {
        'rooms': rooms,
        'topics': topics,
        'room_count': room_count,
        'user_profile': user_profile  # Pass the user profile data to the template
    }
    return render(request, 'base/home.html', context)


@login_required(login_url='login')
def ProfileInfo(request, pk):
    user = User.objects.get(id=pk)  # Fetch user based on primary key (id)
    context = {'user': user}  # Pass the user object to the template
    return render(request, 'base/profile_info.html', context)







@login_required
def send_connection_request(request, user_id):
    receiver = get_object_or_404(User, id=user_id)

    # Prevent sending a connection request to yourself
    if receiver != request.user:
        # Check if the connection already exists in either direction
        if not Connection.objects.filter(user=request.user, connection=receiver).exists() and \
           not Connection.objects.filter(user=receiver, connection=request.user).exists():

            # Create the connection request
            ConnectionRequest.objects.create(sender=request.user, receiver=receiver)
            messages.success(request, f"Connection request sent to {receiver.username}.")
        else:
            messages.error(request, "You are already connected or a request is pending.")
    else:
        messages.error(request, "You cannot send a connection request to yourself.")
    
    return redirect('home')

# Accept Connection Request

@login_required
def accept_connection_request(request, request_id):
    connection_request = get_object_or_404(ConnectionRequest, id=request_id)

    if connection_request.receiver == request.user:
        connection_request.is_accepted = True
        connection_request.save()

        try:
            # Check if the connection already exists in either direction
            Connection.objects.create(user=connection_request.sender, connection=connection_request.receiver)
            Connection.objects.create(user=connection_request.receiver, connection=connection_request.sender)
            messages.success(request, f"You are now connected with {connection_request.sender.username}.")
        except IntegrityError:
            messages.error(request, "You are already connected to this user.")
    else:
        messages.error(request, "You cannot accept this request.")
    return redirect('home')

# View Connections

@login_required
def view_connections(request, pk):
    user = get_object_or_404(User, pk=pk)
    connections = Connection.objects.filter(Q(user=user) | Q(connection=user))
    suggested_connections = User.objects.exclude(pk=user.pk)

    context = {
        'connections': connections,
        'suggested_connections': suggested_connections,  # Pass all users as suggested
        'user': user
    }
    return render(request, 'base/connections.html', context)




@login_required
def message_room(request, user_id=None):
    connections = Connection.objects.filter(Q(user=request.user) | Q(connection=request.user))

    selected_user = None
    room_messages = []

    if user_id:
        selected_user = get_object_or_404(User, pk=user_id)
        room_messages = Message.objects.filter(
            Q(sender=request.user, recipient=selected_user) | Q(sender=selected_user, recipient=request.user)
        ).order_by('timestamp')

    # Handle AJAX requests for message content only
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('messages_fragment.html', {
            'room_messages': room_messages,
        })
        return JsonResponse({'html': html})  # Send back only the message HTML, not the full page

    # For regular requests, render the full template
    context = {
        'connections': connections,
        'room_messages': room_messages,
        'selected_user': selected_user,
    }
    return render(request, 'message.html', context)



@login_required
def load_messages_fragment(request, user_id):
    """Fetch all previous messages between the two users."""
    selected_user = get_object_or_404(User, pk=user_id)
    
    # Retrieve all messages between the logged-in user and the selected user
    room_messages = Message.objects.filter(
        Q(sender=request.user, recipient=selected_user) | 
        Q(sender=selected_user, recipient=request.user)
    ).order_by('timestamp')  # Order by timestamp to show the conversation in chronological order

    # Render the message fragment with all previous messages
    html = render_to_string('messages_fragment.html', {
        'room_messages': room_messages
    })

    return JsonResponse({'html': html})

@csrf_protect
@login_required
def send_message(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            content = data.get('content')
            recipient_id = data.get('recipient')

            if not content or not recipient_id:
                return JsonResponse({"status": "error", "message": "Missing content or recipient"}, status=400)

            recipient = get_object_or_404(User, pk=recipient_id)

            # Create and save the message
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
            )

            # Send success response with relevant data
            return JsonResponse({
                "status": "success", 
                "message": "Message sent!",
                "data": {
                    "sender": request.user.full_name,
                    "recipient": recipient.full_name,
                    "content": message.content,
                    "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)


@login_required
def message_feed(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    room_messages = Message.objects.filter(
        Q(sender=request.user, recipient=selected_user) | Q(sender=selected_user, recipient=request.user)
    ).order_by('timestamp')

    context = {
        'selected_user': selected_user,
        'room_messages': room_messages,
    }
    return render(request, 'base/message_feed.html', context)






