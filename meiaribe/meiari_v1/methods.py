import datetime
import hashlib
import random
import time
from pathlib import Path

import boto3
import jwt
from django.conf import settings
from django.core.mail import send_mail
from google import genai
from google.genai import errors as genai_errors

from .models import OTPTable


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

        # Replace any previous OTP so only the latest one is valid
        OTPTable.objects.filter(user=user).delete()
        OTPTable.objects.create(user=user, otp=otp)

        # Email details
        subject = "Your OTP Code"
        message = f"Your OTP code is {otp}. Please use this to verify your account."

        # Send the OTP email
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.cug_email_address])

        print(f"✅ OTP sent to {user.cug_email_address} and stored in OTPTable.")
        return otp


def users_encode_token(user_id: str, role: str):
    payload = {"id": user_id, "role": role}
    payload["exp"] = datetime.datetime.now(
        tz=datetime.timezone.utc
    ) + datetime.timedelta(days=7)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token

def decode_token(token: str):
    de_value = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    return de_value

def generate_filename(base_name="generated_report"):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}"


_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not settings.GOOGLE_GEMINI_API_KEY:
            raise RuntimeError("GOOGLE_GEMINI_API_KEY is not set.")
        _gemini_client = genai.Client(api_key=settings.GOOGLE_GEMINI_API_KEY)
    return _gemini_client

def get_gemini_response(prompt, attempts=4):
    """
    Function to interact with the Gemini API. Retries transient overload /
    rate-limit errors (503, 429) with exponential backoff.
    """
    for attempt in range(attempts):
        try:
            response = get_gemini_client().models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
            return response.text
        except genai_errors.APIError as e:
            if e.code not in (429, 500, 503) or attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)

def sample_gemini_response(sender, receiver, content_body_1, content_body_2):
    """
    Function to generate a sample response from Gemini Flash API.
    """
    prompt = f"From: {sender}\nTo: {receiver}\n\n{content_body_1}\n\n{content_body_2} create a report using this data."
    response = get_gemini_response(prompt)
    return response


class ReportStorage:
    """
    Stores generated report text in S3 when a bucket is configured, otherwise
    under MEDIA_ROOT so the report flow works in local development.
    """

    def __init__(self):
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME

    @property
    def uses_s3(self):
        return bool(self.bucket)

    def _s3_client(self):
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_S3_REGION_NAME,
        )

    def _local_path(self, key):
        root = Path(settings.MEDIA_ROOT).resolve()
        path = (root / key).resolve()
        if root not in path.parents:
            raise ValueError("Invalid report path.")
        return path

    def save(self, key, text):
        if self.uses_s3:
            self._s3_client().put_object(
                Bucket=self.bucket,
                Key=key,
                Body=text.encode("utf-8"),
                ContentType="text/plain",
            )
            return
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, key):
        if self.uses_s3:
            s3_object = self._s3_client().get_object(Bucket=self.bucket, Key=key)
            return s3_object["Body"].read().decode("utf-8")
        return self._local_path(key).read_text(encoding="utf-8")
