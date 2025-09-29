from django.http import HttpResponse, HttpResponseRedirect
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import base64
from email.mime.text import MIMEText
from django.urls import reverse

TOKEN_PATH = "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def send_test_email(request):
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If no valid creds, redirect to start OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            return HttpResponseRedirect(reverse('start_gmail_auth'))

    service = build("gmail", "v1", credentials=creds)

    message = MIMEText("Hello")
    message["to"] = "johanneskarasikweb@gmail.com"
    message["subject"] = "Test Email"

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    send_result = service.users().messages().send(
        userId="me", body={"raw": raw_message}
    ).execute()

    return HttpResponse(f"Email sent! ID: {send_result['id']}")