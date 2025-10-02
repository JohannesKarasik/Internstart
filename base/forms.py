from django.forms import ModelForm
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.forms import UserCreationForm
from .models import Room, User
from django.forms import modelformset_factory
from .models import Room, RoomFile
from django import forms
from .models import ListingType, JobListing
from .models import Room, Topic






# forms.py

# Step 1: Company Info
class EmployerCompanyForm(forms.Form):
    company_name = forms.CharField(
        max_length=255,
        required=True,
        label="Which company do you represent?",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter company name',
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )
    company_location = forms.CharField(
        max_length=255,
        required=True,
        label="Where is your company located?",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter company location',
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )
    industry = forms.CharField(
        max_length=255,
        required=True,
        label="Which industry are you in?",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter industry',
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )

# Step 2: Personal Info
class EmployerPersonalForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={'placeholder': 'Enter email', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'})
    )
    role_at_company = forms.CharField(
        max_length=255,
        required=True,
        label="Your role at the company",
        widget=forms.TextInput(attrs={'placeholder': 'Enter your role', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'})
    )

    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']

    def save(self, commit=True, company_data=None):
        user = super().save(commit=False)
        user.role = 'employer'
        if company_data:
            user.occupation = company_data['industry']
            user.location = company_data['company_location']
            user.company_name = company_data['company_name']
        if commit:
            user.save()
        return user

class StudentCreationForm(UserCreationForm):
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class StudentCreationForm(UserCreationForm):
    # Explicitly declare resume so we can enforce required + basic validation
    resume = forms.FileField(
        required=True,
        help_text="Upload your resume as PDF or DOCX.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"})
    )

    class Meta:
        model = User
        # keep the same fields you already render, just ensure resume is included
        fields = ['full_name', 'email', 'password1', 'password2', 'resume']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # keep current behavior and simply enforce requireds
        self.fields['full_name'].required = True
        self.fields['email'].required = True
        self.fields['resume'].required = True

    def clean_resume(self):
        f = self.cleaned_data.get('resume')
        if not f:
            raise forms.ValidationError("You must upload a resume to continue.")
        # Optional, lightweight checks (safe to keep or remove)
        import os
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in {'.pdf', '.doc', '.docx'}:
            raise forms.ValidationError("Resume must be a PDF or Word document (.pdf, .doc, .docx).")
        if getattr(f, 'size', 0) > 10 * 1024 * 1024:  # 10 MB
            raise forms.ValidationError("Resume file is too large (max 10MB).")
        return f

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'  # keep your current logic
        if commit:
            user.save()
        return user



from django import forms
from .models import Room


LISTING_CHOICES = [
    ('internship', 'Internship'),
    ('student_jobs', 'Student Jobs'),
]


class RoomForm(forms.ModelForm):
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        empty_label="Select Internship or Student Jobs",
        widget=forms.Select(attrs={
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )

    class Meta:
        model = Room
        fields = ['company_name', 'location', 'job_title', 'description', 'topic', 'logo']
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'Enter company name', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'}),
            'location': forms.TextInput(attrs={'placeholder': 'Enter company location', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'}),
            'job_title': forms.TextInput(attrs={'placeholder': 'Enter job or internship title', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'}),
            'description': forms.Textarea(attrs={'placeholder': 'Enter a description', 'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc; height:120px;'}),
            'logo': forms.ClearableFileInput(attrs={'style': 'margin-top:10px;'}),
        }

RoomFileFormSet = modelformset_factory(RoomFile, fields=('file',), extra=3)  # 'extra=3' means it will handle 3 file inputs initially


from django.forms import ModelForm





class UserForm(forms.ModelForm):
    resume = forms.FileField(
        required=False,
        widget=forms.FileInput  # no “clear” checkbox
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'resume']


    