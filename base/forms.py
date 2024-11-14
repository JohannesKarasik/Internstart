from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm
from .models import Room, User
from django.forms import modelformset_factory
from .models import Room, RoomFile
from django import forms



class MyUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'occupation', 'location', 'password1', 'password2']

def __init__(self, *args, **kwargs):
        super(MyUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['full_name'].required = True  # Ensure full_name is required

class RoomForm(ModelForm):
    class Meta:
        model = Room
        fields = ['description'] 



RoomFileFormSet = modelformset_factory(RoomFile, fields=('file',), extra=3)  # 'extra=3' means it will handle 3 file inputs initially


from django.forms import ModelForm
from .models import User

class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'bio', 'occupation', 'location', 'avatar', 'background']


    