from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.forms import modelformset_factory
from .models import Room, RoomFile, Topic, ListingType, JobListing
from django.utils.translation import gettext_lazy as _


User = get_user_model()




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
        user.occupation = company_data.get('industry')
        user.location = company_data.get('company_location')
        user.company_name = company_data.get('company_name')
    if commit:
        user.save()
    return user



User = get_user_model()

class StudentCreationForm(UserCreationForm):
    # Resume upload
    resume = forms.FileField(
        required=False,
        help_text=_("Upload your resume as PDF or DOCX (optional)."),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"})
    )


    # Desired job title field (replaces industry)
    desired_job_title = forms.CharField(
        max_length=150,
        required=True,
        label=_("What's your desired job title?"),
        widget=forms.TextInput(attrs={
            'placeholder': _('e.g. Marketing Intern, Software Developer, Analyst'),
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;',
        })
    )

    # Job type dropdown
    job_type = forms.ChoiceField(
        choices=[('', _('Select job type'))] + User.JOB_TYPE_CHOICES,  # ✅ translated
        required=True,
        label=_("What type of job are you looking for?"),
        widget=forms.Select(attrs={
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;',
        })
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'email',
            'resume',
            'desired_job_title',
            'job_type',
            'willing_to_relocate',
        ]


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # remove password confirmation field
        if "password2" in self.fields:
            del self.fields["password2"]

        # placeholders
        self.fields['full_name'].widget.attrs.update({
            'placeholder': _("Your full name"),
            'autocomplete': 'name',
            'class': 'form__control',
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': _("you@mail.com"),
            'autocomplete': 'email',
            'class': 'form__control',
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': _("Create a password"),
            'autocomplete': 'new-password',
            'class': 'form__control',
        })

        # required
        self.fields['full_name'].required = True
        self.fields['email'].required = True
        self.fields['willing_to_relocate'].required = True
        self.fields['desired_job_title'].required = True
        self.fields['job_type'].required = True


    def clean_resume(self):
        f = self.cleaned_data.get('resume')
        if not f:
            return None  # no resume uploaded — totally fine

        import os
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in {'.pdf', '.doc', '.docx'}:
            raise forms.ValidationError("Resume must be a PDF or Word document (.pdf, .doc, .docx).")

        if getattr(f, 'size', 0) > 10 * 1024 * 1024:
            raise forms.ValidationError("Resume file is too large (max 10MB).")

        return f


    def save(self, commit=True):
            user = super().save(commit=False)
            user.role = 'student'
            # ❌ removed country assignment. done in view
            user.desired_job_title = self.cleaned_data['desired_job_title']
            user.job_type = self.cleaned_data['job_type']
            user.willing_to_relocate = self.cleaned_data['willing_to_relocate']

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

    country = forms.ChoiceField(
        choices=Room.COUNTRY_CHOICES,
        required=False,
        label="Country",
        widget=forms.Select(attrs={
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )



    job_type = forms.ChoiceField(
        choices=Room.JOB_TYPE_CHOICES,
        required=False,
        label="What type of job is this?",
        widget=forms.Select(attrs={
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;'
        })
    )


        # Willing to relocate?
    willing_to_relocate = forms.ChoiceField(
        choices=[
            ('', 'Select an option'),
            ('yes', 'Yes'),
            ('no', 'No'),
            ('maybe', 'Maybe'),
        ],
        required=True,
        label=_("Are you willing to relocate for work?"),
        widget=forms.Select(attrs={
            'style': 'width:100%; padding:12px; border-radius:8px; border:1px solid #ccc;',
        })
    )


    class Meta:
        model = User
        fields = [
            'full_name',
            'email',
            'resume',
            'desired_job_title',
            'job_type',
            'willing_to_relocate',   # <— ADD THIS
        ]

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


    