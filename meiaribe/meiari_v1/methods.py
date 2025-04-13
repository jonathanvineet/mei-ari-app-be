import hashlib
import os
import random
from django.conf import settings
from django.core.mail import send_mail
from .models import OTPTable
import jwt
from rest_framework.response import Response
from datetime import datetime
import google.generativeai as genai
from django.conf import settings
import datetime


def encrypt_password(raw_password):
    salt = hashlib.sha256()
    salt.update(raw_password.encode('utf-8'))
    salt_bytes = salt.digest()

    hashed_password = hashlib.sha256()
    hashed_password.update(raw_password.encode('utf-8') + salt_bytes)
    hashed_password_bytes = hashed_password.digest()

    return hashed_password_bytes.hex()

class EmailService:
    def send_otp_email(self, user):
        """Generate OTP, store it in the database, and send it via email."""
        otp = str(random.randint(1000, 9999))  # Generate a 4-digit OTP

        # Store OTP in OTPTable
        OTPTable.objects.create(user=user, otp=otp)

        # Email details
        subject = "Your OTP Code"
        message = f"Your OTP code is {otp}. Please use this to verify your account."

        # Send the OTP email
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.cug_email_address])

        print(f"✅ OTP {otp} sent to {user.email} and stored in OTPTable.")
        
        
def users_encode_token(user_id: str, role: str):
    print("Generating token...")
    payload = {"id": user_id, "role": role}
    payload["exp"] = datetime.datetime.now(
        tz=datetime.timezone.utc
    ) + datetime.timedelta(days=7)
    token = jwt.encode(payload, "user_key", algorithm="HS256")
    print("Token generated successfully.")
    return token

def decode_token(token: str):
    de_value = jwt.decode(token, "user_key", algorithms=["HS256"])
    return de_value 

def generate_filename(base_name="generated_report"):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}"

# Configure the API key
genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)

def get_gemini_response(prompt):
    """
    Function to interact with Gemini Flash API.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")  # Use "gemini-pro" or "gemini-flash"
    response = model.generate_content(prompt)
    return response.text

def sample_gemini_response(sender, receiver, content_body_1, content_body_2):
    """
    Function to generate a sample response from Gemini Flash API.
    """
    prompt = f"From: {sender}\nTo: {receiver}\n\n{content_body_1}\n\n{content_body_2} create a report using this data."
    response = get_gemini_response(prompt)
    return response
