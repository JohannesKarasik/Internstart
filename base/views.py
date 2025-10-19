from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import base64
from email.mime.text import MIMEText
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from .models import Room, Topic, User
from .forms import RoomForm, UserForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
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
from docx import Document

from django.contrib.auth import get_user_model
User = get_user_model()

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
from .forms import  StudentCreationForm
from .forms import EmployerCompanyForm, EmployerPersonalForm
from django.utils import timezone
from .models import DailySwipeQuota

import logging
from docx import Document

from django.shortcuts import render, redirect
from .forms import UserForm
# views.py
from django.conf import settings
from django.conf import settings
from django.shortcuts import redirect
from google_auth_oauthlib.flow import Flow
import os
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import RoomForm, UserForm, EmployerCompanyForm, EmployerPersonalForm
from django.http import JsonResponse
from django import template
import fitz  # PyMuPDF
import docx

from .models import UserGoogleCredential
from google.oauth2.credentials import Credentials

from google_auth_oauthlib.flow import Flow

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from django.http import HttpResponse
import os
import json
import threading

from django.core.mail import EmailMultiAlternatives
# views.py
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
import mimetypes
import os
from django.contrib.auth import get_user_model
# views.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import os
from django.core.mail import send_mail
from django.views.decorators.http import require_POST
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from .models import SavedJob, Room   # adjust import to your model names

import re

# views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import SavedJob

import re
from django.core.paginator import Paginator



def sanitize_letter(raw: str, company_name: str = "") -> str:
    if not raw:
        return ""
    txt = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Drop top “letterhead” lines until a greeting
    lines = txt.split("\n")
    keywords = {"your name","your address","city","zip","email","phone","date","company address","hiring manager"}
    start = 0
    for i, l in enumerate(lines):
        s = l.strip().lower()
        if re.match(r'^(hello,|dear\b)', s):
            start = i
            break
        if s in (company_name or "").lower():
            continue
        if not s or any(k in s for k in keywords) or re.search(r'\d{1,5}\s+\w+', s):
            continue
        # keep scanning until we see a greeting
    else:
        # no greeting found; drop obvious placeholders at top
        trimmed, skipping = [], True
        for l in lines:
            s = l.strip().lower()
            if skipping and (not s or any(k in s for k in keywords) or s == (company_name or "").lower()):
                continue
            skipping = False
            trimmed.append(l)
        lines = trimmed
        txt = "\n".join(lines).lstrip()
    if start:
        txt = "\n".join(lines[start:]).lstrip()

    # Normalize greeting
    txt = re.sub(r'^\s*dear\s+hiring\s+manager[.,]?\s*', "Hello,\n\n", txt, flags=re.IGNORECASE)

    # Remove ANY bracket characters (even unmatched), incl. fullwidth variants
    txt = re.sub(r'[\[\]\(\)［］（）]', '', txt)

    # Tidy punctuation/spacing/newlines
    txt = re.sub(r'\s+([,.;:!?])', r'\1', txt)
    txt = re.sub(r'([,.;:!?])([^\S\n]+)', r'\1 ', txt)
    txt = re.sub(r'[ \t]{2,}', ' ', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    txt = txt.strip()

    if not re.match(r'^(hello,|dear\b)', txt, flags=re.IGNORECASE):
        txt = "Hello,\n\n" + txt

    return txt



@login_required
def saved_jobs_json(request):
    saved = SavedJob.objects.filter(user=request.user).select_related('room')
    return JsonResponse({
        'jobs': [
            {
                'id': s.room.id,
                'title': s.room.job_title,
                'company': s.room.company_name,
                'location': s.room.location,
                'logo': s.room.logo.url if s.room.logo else '',
            }
            for s in saved
        ]
    })

# ---- SEND APPLICATION (sends provided cover letter; still strips [placeholders]) ----
@csrf_exempt
@login_required
def send_application(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body or "{}")
            coverletter = data.get("coverletter", "")
            room_id = data.get("room_id")

            if not coverletter:
                return JsonResponse({"success": False, "error": "No cover letter provided."})
            if not room_id:
                return JsonResponse({"success": False, "error": "Missing room ID"})

            # Fetch the room (employer/job listing)
            room = get_object_or_404(Room, id=room_id)

            # Clean the cover letter
            coverletter = re.sub(r'\[[^\]]*\]', '', coverletter)  # remove only square brackets
            if 'sanitize_letter' in globals():
                coverletter = sanitize_letter(coverletter)
            coverletter = re.sub(r'\n{3,}', '\n\n', coverletter).strip()

            # Get Gmail credentials for current user
            user_creds = UserGoogleCredential.objects.filter(user=request.user).first()
            if not user_creds:
                return JsonResponse({
                    "success": False,
                    "error": "OAuth required",
                    "redirect": reverse('start_gmail_auth')
                })

            creds = Credentials(
                token=user_creds.token,
                refresh_token=user_creds.refresh_token,
                token_uri=user_creds.token_uri,
                client_id=user_creds.client_id,
                client_secret=user_creds.client_secret,
                scopes=user_creds.scopes.split()
            )

            # Refresh token if needed
            if not creds.valid and creds.refresh_token:
                creds.refresh(Request())
                user_creds.token = creds.token
                user_creds.save()
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    return JsonResponse({
                        "success": False,
                        "error": "OAuth required",
                        "redirect": reverse('start_gmail_auth')
                    })

            # Gmail service
            service = build("gmail", "v1", credentials=creds)

            # Build the email
            message = MIMEText(coverletter, _subtype='plain', _charset='utf-8')
            message["to"] = room.email if room.email else "fallback@internstart.com"
            message["subject"] = f"Application for {room.job_title or 'internship role'} at {room.company_name or 'your team'}"

            # Encode and send
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return JsonResponse({"success": True, "message_id": send_result.get("id")})

        except Exception as e:
            import traceback
            print("Error sending application:", e)
            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method."})




from io import BytesIO
from django.core.files.storage import default_storage
import os, fitz
from docx import Document

def get_user_resume_text(user) -> str:
    f = getattr(user, "resume", None)
    if not f:
        print("[RESUME] no FileField on user")
        return ""

    # if FieldFile with actual file
    if hasattr(f, "path") and getattr(f, "name", ""):
        path = f.path
    else:
        # treat .resume as a string path relative to static/images/resumes
        path = os.path.join(settings.BASE_DIR, 'static', 'images', 'resumes', str(f))

    if not os.path.exists(path):
        print("[RESUME] file not found at", path)
        return ""

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            import fitz
            text = ""
            with fitz.open(path) as pdf:
                for page in pdf:
                    text += page.get_text("text")
            return text.strip()
        elif ext == ".docx":
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs).strip()
        else:
            with open(path, "r", errors="ignore") as fh:
                return fh.read().strip()
    except Exception as e:
        print("[RESUME] failed to read:", e)
        return ""




@csrf_exempt
@login_required
def generate_coverletter(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)



from django.views.decorators.http import require_POST
from django.utils import timezone



import threading
import os
import json
import base64
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from email.mime.text import MIMEText


# --- Settings for Gmail OAuth ---
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'credentials.json')


def gmail_callback(request):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://127.0.0.1:8000/gmail/callback/'
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    creds = flow.credentials

    # 🔹 Figure out which user we’re linking credentials to
    new_user_id = request.session.pop('new_user_id', None)
    if new_user_id:
        # This OAuth was triggered immediately after registration
        user = get_object_or_404(User, id=new_user_id)
    else:
        # This OAuth was triggered by a logged-in user later
        user = request.user

    # 🔹 Save or update their Gmail credentials
    UserGoogleCredential.objects.update_or_create(
        user=user,
        defaults={
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': ' '.join(creds.scopes)
        }
    )

    # ✅ mark onboarding as done so it won't show again
    user.onboarding_shown = True
    user.save()

    messages.success(request, "Gmail connected successfully.")
    return redirect('swipe_view')   # ⬅️ go back to swipe page instead of check_email.html

from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
import base64, json, re
from django.utils import timezone
import traceback

from openai import OpenAI
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes


def discover(request):
    user = request.user
    qs = Room.objects.all()

    if user.is_authenticated:
        swiped_ids = SwipedJob.objects.filter(user=user).values_list("room_id", flat=True)
        qs = qs.exclude(id__in=swiped_ids)

    return render(request, "swipe_component.html", {"rooms": qs})

from .models import SwipedJob


@csrf_exempt
@login_required
def apply_swipe_job(request):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    print("DEBUG request.user.id:", request.user.id)
    print("DEBUG request.user.email:", request.user.email)
    print("DEBUG request.user.resume.name:", getattr(getattr(request.user, "resume", None), "name", None))

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})

    today = timezone.localdate()
    quota, _ = DailySwipeQuota.objects.get_or_create(user=request.user, date=today)

    SWIPE_LIMITS = {"free": 3, "starter": 15, "pro": 30, "elite": 45}
    tier = (getattr(request.user, "subscription_tier", "free") or "free").lower()
    limit = SWIPE_LIMITS.get(tier, 5)

    if quota.count >= limit:
        return JsonResponse({
            "success": False,
            "error": f"Daily swipe limit ({limit}) reached for your {tier.capitalize()} plan."
        })

    quota.count += 1
    quota.save()

    try:
        data = json.loads(request.body or "{}")
        room_id = data.get("room_id")
        if not room_id:
            return JsonResponse({"success": False, "error": "Missing room ID"})

        room = Room.objects.get(id=room_id)

        # ✅ Ensure swipe is recorded immediately
        SwipedJob.objects.get_or_create(user=request.user, room=room)

        company_name = room.company_name or ""
        role_title   = getattr(room, "job_title", "") or ""
        location     = getattr(room, "location", "") or ""
        job_desc     = getattr(room, "description", "") or ""

        # ✅ resume text
        resume_text = get_user_resume_text(request.user) or ""
        print("[DEBUG] resume_text first 200 chars:", resume_text[:200])

        res_field = getattr(request.user, 'resume', None)
        print("user.resume.name:", getattr(res_field, 'name', None))
        if res_field and getattr(res_field, 'name', ''):
            # Some storage backends may not have .path (e.g., S3). Guard access.
            try:
                print("user.resume.path:", res_field.path)
            except Exception:
                print("user.resume has no local path attribute")
        else:
            print("user has no resume uploaded")

        # GPT prompt (UNCHANGED)
        full_prompt = f"""
Below is the full resume text of the applicant. Then the job description.

Write a **first-person** professional plain-text cover letter of at most 250 words for the job.

You MUST:
- Write in first person (“Hello, I’m …” or “My name is …”), not third person.
- Start by introducing yourself by name and mentioning your current or most recent school/university.
- Bring up relevant work experience early (in the first few sentences).
- Use as many real details from the resume as possible; if something is not in the resume, do NOT mention it.
- Keep it under 250 words.
- If no named recipient, start with "Hello,".
- End the letter with a short sentence telling the recipient that your resume is attached (e.g., “I have attached my resume below for your review.”).
- Return only the letter body (no subject line, no signature placeholders).
- Make it sound like a natural cover letter you’d actually send.

=== RESUME TEXT ===
{resume_text or "not provided"}

=== JOB ===
Company: {company_name or "unknown"}
Role: {role_title or "unknown"}
Location: {location or "unknown"}
Description:
{job_desc or "not provided"}
"""

        print("[DEBUG] prompt first 500 chars:", full_prompt[:500])

        coverletter = ""
        # Generate cover letter, but don't fail the swipe if GPT errors.
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.1,
            )
            coverletter = (response.choices[0].message.content or "").strip()
            coverletter = re.sub(r'\[[^\]]*\]', '', coverletter)
            coverletter = re.sub(r'\n{3,}', '\n\n', coverletter).strip()
        except Exception as e:
            print("[GPT ERROR]", e)

        # ✅ send via Gmail (multipart with attachment)
        user_creds = UserGoogleCredential.objects.filter(user=request.user).first()
        if not user_creds:
            # Swipe is saved; return success so UI can move on, plus tell client to auth.
            return JsonResponse({
                "success": True,
                "message": "Swipe saved. Gmail OAuth required to send.",
                "needs_oauth": True,
                "redirect": reverse('start_gmail_auth'),
                "coverletter": coverletter,
            })

        try:
            creds = Credentials(
                token=user_creds.token,
                refresh_token=user_creds.refresh_token,
                token_uri=user_creds.token_uri,
                client_id=user_creds.client_id,
                client_secret=user_creds.client_secret,
                scopes=user_creds.scopes.split()
            )
            if not creds.valid and creds.refresh_token:
                creds.refresh(Request())
                user_creds.token = creds.token
                user_creds.save()

            service = build("gmail", "v1", credentials=creds)

            # Build a multipart message
            msg = MIMEMultipart()
            msg["to"] = room.email if room.email else "fallback@internstart.com"
            msg["subject"] = f"Application for {role_title or 'internship role'} at {company_name or 'your team'}"


            # Part 1: cover letter body (fallback body if GPT failed)
            msg.attach(MIMEText(coverletter or "Hello,\n\nPlease find my resume attached.", _subtype='plain', _charset='utf-8'))

            # Part 2: attach resume if available (guard .path)
            attached = False
            if res_field:
                resume_path = None
                try:
                    resume_path = res_field.path
                except Exception:
                    resume_path = None  # e.g., cloud storage without local path
                if resume_path and os.path.exists(resume_path):
                    ctype, encoding = mimetypes.guess_type(resume_path)
                    if ctype is None or encoding is not None:
                        ctype = 'application/octet-stream'
                    maintype, subtype = ctype.split('/', 1)
                    with open(resume_path, 'rb') as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(resume_path))
                        msg.attach(part)
                        attached = True

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return JsonResponse({
                "success": True,
                "message": "Cover letter sent successfully with resume attached" if attached else "Cover letter sent successfully",
                "coverletter": coverletter
            })
        except Exception as e:
            print("[GMAIL ERROR]", e)
            # Still success because the swipe is recorded.
            return JsonResponse({
                "success": True,
                "message": "Swipe saved. Failed to send email via Gmail.",
                "coverletter": coverletter
            })

    except Room.DoesNotExist:
        return JsonResponse({"success": False, "error": "Room not found"})
    except Exception as e:
        traceback.print_exc()
        # If we got here after recording the swipe, the swipe remains saved (autocommit).
        return JsonResponse({"success": True, "message": "Swipe saved, but an error occurred.", "error": str(e)})



def view_resume(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.resume:
        raise Http404("No resume uploaded")
    
    resume_path = user.resume.path
    resume_file = open(resume_path, 'rb')
    
    mime_type, _ = mimetypes.guess_type(resume_path)
    response = FileResponse(resume_file, content_type=mime_type or 'application/pdf')
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(resume_path)}"'
    return response

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'credentials.json')




def start_gmail_auth(request):
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, 'credentials.json'),
        scopes=["https://www.googleapis.com/auth/gmail.send"],
        redirect_uri=request.build_absolute_uri('/gmail/callback/')
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # force Google to show the consent screen again
    )

    request.session['oauth_state'] = state
    return redirect(authorization_url)


def get_quota(request):
    today = timezone.localdate()
    quota, _ = DailySwipeQuota.objects.get_or_create(user=request.user, date=today)

    left = max(0, quota.limit - quota.count)
    return JsonResponse({'left': left, 'limit': quota.limit})

@login_required
def send_test_email(request):
    user_creds = UserGoogleCredential.objects.filter(user=request.user).first()
    if not user_creds:
        return HttpResponseRedirect(reverse('start_gmail_auth'))

    creds = Credentials(
        token=user_creds.token,
        refresh_token=user_creds.refresh_token,
        token_uri=user_creds.token_uri,
        client_id=user_creds.client_id,
        client_secret=user_creds.client_secret,
        scopes=user_creds.scopes.split()
    )

    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        # update DB with new token
        user_creds.token = creds.token
        user_creds.save()

    service = build("gmail", "v1", credentials=creds)

    message = MIMEText("Hello")
    message["to"] = "johanneskarasikweb@gmail.com"
    message["subject"] = "Test Email"

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

    return HttpResponse("Email sent from your Gmail!")


def gmail_callback(request):
    state = request.session.get('oauth_state')
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, 'credentials.json'),
        scopes=SCOPES,
        state=state,
        redirect_uri=request.build_absolute_uri(reverse('gmail_callback'))
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    creds = flow.credentials

    # save creds to user
    new_user_id = request.session.pop('new_user_id', None)
    if new_user_id:
        user = get_object_or_404(User, id=new_user_id)
    else:
        user = request.user

    UserGoogleCredential.objects.update_or_create(
        user=user,
        defaults={
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': ' '.join(creds.scopes)
        }
    )
    messages.success(request, "Gmail connected successfully.")
    return redirect('swipe_view')

def classify_user_category(user):
    if not user.resume:
        return None

    resume_text = extract_resume_text(user.resume)
    if not resume_text.strip():
        return None

    # ✅ Reuse global client
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a career classifier."},
            {"role": "user", "content": f"Classify this resume into one of Finance, Accounting, Consulting, Tech, Law. Return only the category: {resume_text}"}
        ],
        temperature=0
    )

    category = response.choices[0].message.content.strip()
    user.category = category
    user.save()
    return category





def health_check(request):
    return JsonResponse({"status": "ok"})



from django import template
register = template.Library()

@register.filter
def is_image(file_path):
    mime = mimetypes.guess_type(file_path)[0]
    return mime and mime.startswith('image')


def landing_page(request):
    # If user is already logged in, send them to the main app
    if request.user.is_authenticated:
        return redirect('swipe_view')
    return render(request, 'base/landing_page.html')



@login_required
def revoke_google_access(request):
    """
    Fully revoke Gmail OAuth access for the logged-in user.
    After this, the app can no longer send emails on their behalf.
    """
    user_creds = UserGoogleCredential.objects.filter(user=request.user).first()

    if not user_creds:
        messages.info(request, "No connected Google account to revoke.")
        return redirect('update-user')

    # Attempt to revoke with Google API
    try:
        revoke_url = "https://oauth2.googleapis.com/revoke"
        token_to_revoke = user_creds.token or user_creds.refresh_token

        response = requests.post(
            revoke_url,
            params={'token': token_to_revoke},
            headers={'content-type': 'application/x-www-form-urlencoded'},
            timeout=10
        )

        if response.status_code == 200:
            messages.success(request, "Google access successfully revoked.")
        elif response.status_code == 400:
            # Already revoked or invalid token
            messages.info(request, "Google access already revoked or invalid.")
        else:
            messages.warning(
                request,
                f"Google revocation returned unexpected status: {response.status_code}"
            )

    except Exception as e:
        print(f"[GOOGLE REVOKE ERROR] {e}")
        messages.error(request, "Failed to contact Google revoke endpoint.")

    # 🔥 Remove local credentials regardless (for safety)
    user_creds.delete()

    # Optionally flag user as disconnected
    request.user.email_configured = False
    request.user.save()

    return redirect('update-user')


def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('swipe_view')

    if request.method == 'POST':
        # Accept either <input name="username"> or <input name="email">
        raw_identifier = (request.POST.get('username') or request.POST.get('email') or '').strip()
        password = (request.POST.get('password') or '').strip()

        User = get_user_model()
        user = None
        username_to_use = None
        lookup_user = None

        # Resolve identifier to a username (if they typed an email)
        if '@' in raw_identifier:
            try:
                lookup_user = User.objects.get(email__iexact=raw_identifier)
                username_to_use = getattr(lookup_user, 'username', None) or lookup_user.get_username()
            except User.DoesNotExist:
                lookup_user = None
        else:
            username_to_use = raw_identifier
            try:
                lookup_user = User.objects.get(username__iexact=username_to_use)
            except User.DoesNotExist:
                lookup_user = None

        # If the account exists but hasn't been activated yet

        # Authenticate
        if username_to_use:
            user = authenticate(request, username=username_to_use, password=password)

        # Optional fallback if you also have a custom EmailBackend
        if user is None and '@' in raw_identifier:
            user = authenticate(request, email=raw_identifier.lower(), password=password)

        if user is not None:
            login(request, user)
            return redirect('swipe_view')

        messages.error(request, "Username or password is incorrect.")

    from django.conf import settings
    return render(
        request,
        'base/login_register.html',
        {
            'page': page,
            'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,  # ✅ pulled from Gunicorn env
        }
    )


def logoutUser(request):
    logout(request)
    return redirect('home')


def registerPage(request):
    page = 'register'

    if request.method == 'POST':
        # Read which step we're on (default to '1' if missing)
        step = request.POST.get('step', '1')

        # Debug info
        print("🔹 REGISTER POST DETECTED")
        print("STEP:", step)
        print("POST DATA:", dict(request.POST))
        print("FILES:", request.FILES)

        # Bind the full form so entered values stick on re-render
        form = StudentCreationForm(request.POST, request.FILES)

        # === STEP 1 or STEP 2 POST (not final yet) ===
        # Move user to the next step without creating the account
        if step in ['1', '2']:
            next_step = '2' if step == '1' else '3'
            print(f"➡️ Moving from step {step} to {next_step}")
            context = {
                'student_form': form,
                'page': page,
                'show_step': next_step,
            }
            return render(request, 'base/login_register.html', context)

        # === STEP 3 POST (final submit) ===
        if step == '3':
            print("✅ Final step detected, validating form...")
            if form.is_valid():
                user = form.save(commit=False)
                user.role = 'student'
                user.is_active = True         # ✅ activate immediately
                user.save()

                login(request, user)          # ✅ log them in right away
                messages.success(request, "Welcome to Internstart! Your account is ready.")
                print("🎉 User created successfully:", user.email)
                return redirect('swipe_view') # or 'start_gmail_auth' if you want OAuth first

            # If form invalid
            print("❌ FORM ERRORS:", form.errors)
            messages.error(request, 'Please correct the errors below.')
            context = {'student_form': form, 'page': page, 'show_step': '3'}
            return render(request, 'base/login_register.html', context)

    # GET
    form = StudentCreationForm()
    return render(request, 'base/login_register.html', {'student_form': form, 'page': 'register'})

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

@login_required(login_url='app_login')
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


def feed_view(request):
    return render(request, "feed_component.html")

from .models import DailySwipeQuota
from django.utils import timezone

from django.core.paginator import Paginator

@login_required
def swipe_view(request):
    q = request.GET.get('q') or ''
    page = int(request.GET.get('page', 1))
    swiped_ids = SwipedJob.objects.filter(user=request.user).values_list('room_id', flat=True)

    rooms_qs = Room.objects.exclude(id__in=swiped_ids).filter(
        Q(topic__name__icontains=q) |
        Q(description__icontains=q)
    ).order_by('id')

    # ✅ Filter listings by student's profile preferences
    user = request.user
    if getattr(user, 'role', None) == 'student':
        rooms_qs = rooms_qs.filter(
            industry=user.student_industry,
            country=user.country,
            job_type=user.job_type
        )

    paginator = Paginator(rooms_qs, 5)
    rooms = paginator.get_page(page)

    partial = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    topics = Topic.objects.all()[:5]
    room_count = rooms_qs.count()
    today = timezone.localdate()
    quota, _ = DailySwipeQuota.objects.get_or_create(user=request.user, date=today)
    swipes_left = max(0, quota.limit - quota.count)

    first_login = False
    if not request.user.onboarding_shown:
        first_login = True
        request.user.onboarding_shown = True
        request.user.save()

    context = {
        "swipes_left": swipes_left,
        "swipe_limit": quota.limit,
        "rooms": rooms,
        "topics": topics,
        "room_count": room_count,
        "user_profile": request.user,
        "first_login": first_login,
        "email_configured": getattr(request.user, "email_configured", False),
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
        "partial": partial,
    }

    # ✅ Return only card HTML when loading more (AJAX)
    if partial:
        context["rooms"] = rooms.object_list  # ✅ Only the 5 new items
        html = render_to_string("base/swipe_cards.html", context, request=request)
        return HttpResponse(html)

    # ✅ Otherwise return full template
    return render(request, "base/swipe_component.html", context)






@login_required
def swipe_jobs_api(request):
    page = int(request.GET.get("page", 1))   # current page number (1, 2, 3, ...)
    page_size = 5
    offset = (page - 1) * page_size          # calculate offset for slicing

    # Exclude swiped jobs
    swiped_ids = SwipedJob.objects.filter(user=request.user).values_list("room_id", flat=True)

    # Select only the slice you want
    rooms = (
        Room.objects.exclude(id__in=swiped_ids)
        .order_by("id")[offset:offset + page_size]
    )

    # When fetching dynamically (via JS)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "base/swipe_component.html", {"rooms": rooms, "partial": True})

    # When rendering first load
    return render(request, "base/swipe_component.html", {"rooms": rooms, "partial": False})




@login_required
@csrf_exempt
def debug_set_tier(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    data = json.loads(request.body or "{}")
    tier = (data.get("tier") or "free").lower()
    SWIPE_LIMITS = {"free": 3, "starter": 15, "pro": 30, "elite": 45}

    if tier not in SWIPE_LIMITS:
        return JsonResponse({"error": f"Invalid tier '{tier}'"}, status=400)

    request.user.subscription_tier = tier
    request.user.save()

    # update quota for today
    quota, _ = DailySwipeQuota.objects.get_or_create(
        user=request.user, date=timezone.localdate()
    )
    quota.limit = SWIPE_LIMITS[tier]

    # if you want to reset usage on upgrade:
    if quota.count >= quota.limit:
        quota.count = 0  # reset used count on upgrade
    quota.save()

    left = max(0, quota.limit - quota.count)

    return JsonResponse({"tier": tier, "limit": quota.limit, "left": left})


import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.utils.timezone import make_aware
import datetime

from django.contrib.auth import get_user_model
User = get_user_model()


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    # ✅ Subscription completed at checkout
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        customer_email = session.get("customer_email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        tier = session["metadata"].get("tier") if session.get("metadata") else "free"  # ✅ read tier from metadata

        if customer_email:
            try:
                user = User.objects.get(email=customer_email)
                user.stripe_customer_id = customer_id
                user.subscription_status = "active"
                user.subscription_tier = tier  # ✅ set subscription tier
                user.save()

                # ✅ also update today’s swipe quota
                SWIPE_LIMITS = {"free": 3, "starter": 15, "pro": 30, "elite": 45}
                today = timezone.localdate()
                quota, _ = DailySwipeQuota.objects.get_or_create(user=user, date=today)
                quota.limit = SWIPE_LIMITS.get(tier, 5)
                quota.save()

            except User.DoesNotExist:
                pass

    # ✅ Subscription updated (renewal, cancellation, etc.)
    if event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        try:
            user = User.objects.get(stripe_customer_id=customer_id)
            user.subscription_status = subscription["status"]  # e.g. active, past_due, canceled
            # Convert Unix timestamp to datetime
            period_end = datetime.datetime.fromtimestamp(
                subscription["current_period_end"]
            )
            user.subscription_current_period_end = make_aware(period_end)
            user.save()
        except User.DoesNotExist:
            pass

    # ✅ Subscription canceled
    if event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        try:
            user = User.objects.get(stripe_customer_id=customer_id)
            user.subscription_status = "canceled"
            user.subscription_tier = "free"  # downgrade automatically
            user.save()
        except User.DoesNotExist:
            pass

    return HttpResponse(status=200)


@login_required
def create_checkout_session(request, tier):
    prices = {
        "starter": "price_1SDxgh6IJebVII3FaIOLhBkn",  # Stripe price IDs
        "pro": "price_1SCRta6IJebVII3Feda7JGJf",
        "elite": "price_1SDxhc6IJebVII3F87lwDxEC",
    }
    if tier not in prices:
        return JsonResponse({"error": "Invalid tier"}, status=400)

    session = stripe.checkout.Session.create(
        customer_email=request.user.email,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": prices[tier], "quantity": 1}],
        success_url=_absolute(request, "swipe_view") + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=_absolute(request, "swipe_view"),
        metadata={"tier": tier},  # ✅ store tier in Stripe
    )
    return JsonResponse({"id": session.id})



@login_required
@require_POST
def save_job(request):
    data = json.loads(request.body)
    room_id = data.get('room_id')
    if not room_id:
        return JsonResponse({'error': 'Missing room_id'}, status=400)
    try:
        room = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)

    saved, created = SavedJob.objects.get_or_create(user=request.user, room=room)
    return JsonResponse({'status': 'ok', 'created': created})

# views.py
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

def _absolute(request, path_name, **kwargs):
    """
    Safer absolute URL builder that doesn't rely on untrusted Host headers.
    Configure SITE_URL = "https://yourdomain.com" in settings and use that.
    """
    base = getattr(settings, 'SITE_URL', None)
    if base:
        from urllib.parse import urljoin
        return urljoin(base, reverse(path_name, kwargs=kwargs))
    # Fallback to request.build_absolute_uri if you trust your dev host
    return request.build_absolute_uri(reverse(path_name, kwargs=kwargs))



# base/views.py
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def billing_success(request):
    return HttpResponse("Payment successful. You can close this tab.")

@login_required
def billing_cancel(request):
    return HttpResponse("Checkout cancelled. No charges were made.")


def company_profile(request, pk):
    company = get_object_or_404(User, pk=pk)
    return render(request, 'company_profile.html', {'company': company})


@login_required(login_url='app_login')
def createRoom(request):
    # Predefine topics as Internship or Student Job
    topics = Topic.objects.filter(name__in=["Internship", "Student Jobs"])

    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)

        if form.is_valid():
            selected_topic_id = request.POST.get('topic')  
            topic = Topic.objects.get(id=selected_topic_id)

            room = form.save(commit=False)
            room.host = request.user
            room.topic = topic  
            room.save()

            # Handle multiple file uploads (optional company docs, job description PDFs, etc.)
            files = request.FILES.getlist('files')
            for file in files:
                RoomFile.objects.create(room=room, file=file)

            messages.success(request, 'Job listing created successfully!')
            return redirect('home')
        else:
            messages.error(request, 'There was an error creating the listing. Please check the form for errors.')
    else:
        form = RoomForm()

    context = {
        'form': form,
        'topics': topics,  
    }
    return render(request, 'base/room_form.html', context)


@login_required(login_url='app_login')
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


@login_required(login_url='app_login')
def deleteRoom(request, pk):
    room = Room.objects.get(id=pk)

    if request.user != room.host:
        return HttpResponse('Your are not allowed here!!')

    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': room})




@login_required(login_url='app_login')
def updateUser(request):
    user = request.user

    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Profile updated!")
            return redirect('update-user')
    else:
        form = UserForm(instance=user)

    # 🔹 Check if this user has Gmail OAuth connected
    from .models import UserGoogleCredential
    has_gmail_connected = UserGoogleCredential.objects.filter(user=user).exists()

    return render(
        request,
        'base/update-user.html',
        {
            'form': form,
            'user': user,
            'has_gmail_connected': has_gmail_connected,  # ✅ new context variable
        },
    )



@login_required(login_url='app_login')
def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains=q)
    return render(request, 'base/topics.html', {'topics': topics})

@login_required(login_url='app_login')
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


@login_required(login_url='app_login')
def ProfileInfo(request, pk):
    user = User.objects.get(id=pk)  # Fetch user based on primary key (id)
    context = {'user': user}  # Pass the user object to the template
    return render(request, 'base/profile_info.html', context)




@login_required
def cancel_subscription(request):
    """
    Allows a logged-in user to cancel their current subscription.
    This version downgrades them to free immediately (you can expand it later).
    """
    user = request.user
    user.subscription_status = "canceled"
    user.subscription_tier = "free"
    user.save()

    messages.success(request, "Your subscription has been cancelled. You're now on the Free plan.")
    return redirect('update-user')


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






from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

def register_user(request):
    if request.method == 'POST':
        form = StudentCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False   # so they can’t log in until verified
            user.save()

            # Build activation link
            current_site = get_current_site(request)
            subject = 'Activate your account'
            message = render_to_string('activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            send_mail(subject, message, None, [user.email])  # None uses DEFAULT_FROM_EMAIL

            return render(request, 'check_email.html')  # page telling them to check email
        
def activate_account(request, uidb64, token):
    User = get_user_model()
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your account has been activated. You can now log in.")
        return redirect('app_login')  # or whatever your login URL name is
    else:
        messages.error(request, "Activation link is invalid or has expired.")
        return redirect('app_login')
    

def terms_conditions(request):
    return render(request, 'terms_and_conditions.html')

from django.shortcuts import render

def privacy_policy(request):
    """Render Privacy Policy page."""
    return render(request, 'base/privacy_policy.html')
    # or 'base/privacy_policy.html' if you keep it inside base/

from django.shortcuts import render

def about(request):
    return render(request, "base/about.html")


from django.shortcuts import render

def contact(request):
    return render(request, "base/contact.html")
