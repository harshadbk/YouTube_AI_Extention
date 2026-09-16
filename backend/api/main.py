import os
import re
import sys
import logging
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pymongo import ASCENDING, MongoClient
import bcrypt
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

import traceback
import requests

logger = logging.getLogger(__name__)

app = FastAPI()

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print("\n" + "="*50)
        print("!!! CRITICAL SERVER CRASH DETECTED IN CHAT ROUTE !!!")
        print(f"Error Message: {str(e)}")
        print("="*50)
        traceback.print_exc()
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Server Error: {str(e)}"}
        )

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load environment variables from the backend directory regardless of the
# process working directory.
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# Import RAG utilities
from rag import TranscriptUnavailableError, answer_question, extract_video_id, get_transcript

# Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "youtube_ai_extension")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "messages")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "khataleharshad78@gmail.com")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
VERIFICATION_CODE_TTL_MINUTES = 15
mongo_client = None
messages = None
users = None
security = HTTPBearer()

def init_db():
    global mongo_client, messages, users
    if not MONGODB_URI or not JWT_SECRET:
        raise RuntimeError("MONGODB_URI and JWT_SECRET must be configured")

    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command("ping")
    database = mongo_client[MONGODB_DATABASE]
    messages = database[MONGODB_COLLECTION]
    users = database["users"]
    messages.create_index([("user", ASCENDING), ("url", ASCENDING), ("created_at", ASCENDING)])
    users.create_index("email", unique=True)

# Initialize DB on startup
init_db()

@app.get("/")
async def root():
    return {"status": "ok"}

class AuthRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    phone: str | None = None

class VerifyEmailRequest(BaseModel):
    email: str
    code: str

class ResendVerificationRequest(BaseModel):
    email: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    password: str

class ProfileUpdateRequest(BaseModel):
    full_name: str
    phone: str

class QueryRequest(BaseModel):
    url: str
    question: str
    transcript_text: str | None = None
    video_title: str | None = None

def send_verification_email(email: str, code: str, subject: str = "Your YouTube AI Assistant verification code", message_label: str = "verification"):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY must be configured")

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": email}]}],
            "from": {"email": SENDGRID_FROM_EMAIL, "name": "YouTube AI Assistant"},
            "reply_to": {"email": SENDGRID_FROM_EMAIL, "name": "YouTube AI Assistant"},
            "subject": subject,
            "content": [{
                "type": "text/plain",
                "value": (
                    f"Your YouTube AI Assistant {message_label} code is {code}.\n\n"
                    f"This code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes."
                ),
            }, {
                "type": "text/html",
                "value": (
                    f"<p>Your YouTube AI Assistant {message_label} code is:</p>"
                    f"<p style='font-size:28px;font-weight:bold;letter-spacing:6px'>{code}</p>"
                    f"<p>This code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes.</p>"
                ),
            }],
        },
        timeout=15,
    )
    if response.status_code >= 300:
        logger.error("SendGrid rejected verification email: %s", response.text)
        try:
            details = response.json().get("errors", [])
            message = details[0].get("message", "SendGrid rejected the request") if details else "SendGrid rejected the request"
        except ValueError:
            message = "SendGrid rejected the request"
        raise RuntimeError(f"SendGrid error ({response.status_code}): {message}")
    logger.info(
        "Verification email accepted by SendGrid for %s with status %s and message id %s",
        email,
        response.status_code,
        response.headers.get("X-Message-Id", "unknown"),
    )

def create_token(user_id: str):
    return jwt.encode({"sub": user_id}, JWT_SECRET, algorithm="HS256")

def create_google_state():
    expires_at = datetime.now(timezone.utc).timestamp() + 600
    return jwt.encode({"purpose": "google_oauth", "exp": expires_at}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = users.find_one({"_id": user_id}, {"_id": 1, "email": 1, "full_name": 1, "phone": 1})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/auth/register")
async def register(req: AuthRequest):
    email = req.email.strip().lower()
    full_name = (req.full_name or "").strip()
    phone = (req.phone or "").strip()
    if "@" not in email or len(req.password) < 8 or not full_name or not phone:
        raise HTTPException(status_code=400, detail="Name, phone, valid email, and a password with at least 8 characters are required")

    user_id = str(uuid4())
    verification_code = f"{secrets.randbelow(1000000):06d}"
    user = {
        "_id": user_id,
        "email": email,
        "full_name": full_name,
        "phone": phone,
        "password_hash": bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode(),
        "email_verified": False,
        "verification_code_hash": bcrypt.hashpw(verification_code.encode(), bcrypt.gensalt()).decode(),
        "verification_expires_at": datetime.now(timezone.utc).timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        users.insert_one(user)
    except Exception as error:
        if getattr(error, "code", None) == 11000:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise
    try:
        send_verification_email(email, verification_code)
    except Exception as error:
        users.delete_one({"_id": user_id})
        logger.exception("Verification email failed for %s", email)
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"verification_required": True, "email": email}

@app.get("/auth/google/login")
async def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    from fastapi.responses import RedirectResponse
    from urllib.parse import urlencode

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": create_google_state(),
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

@app.get("/auth/google/callback")
async def google_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    from fastapi.responses import RedirectResponse
    from urllib.parse import urlencode

    if error:
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=cancelled")
    if not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=missing_response")
    try:
        state_payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if state_payload.get("purpose") != "google_oauth":
            raise JWTError
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        profile_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        email = profile.get("email", "").strip().lower()
        if not email or not profile.get("email_verified"):
            raise ValueError("Google email is not verified")

        user = users.find_one({"email": email})
        if user:
            user_id = user["_id"]
            users.update_one({"_id": user_id}, {"$set": {"email_verified": True}})
        else:
            user_id = str(uuid4())
            users.insert_one({
                "_id": user_id,
                "email": email,
                "full_name": profile.get("name", "").strip(),
                "phone": "",
                "password_hash": bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode(),
                "email_verified": True,
                "created_at": datetime.now(timezone.utc),
            })
        fragment = urlencode({"token": create_token(user_id), "email": email})
        return RedirectResponse(f"{FRONTEND_URL}/auth/google/callback#{fragment}")
    except Exception:
        logger.exception("Google sign-in failed")
        return RedirectResponse(f"{FRONTEND_URL}/login?google_error=failed")

@app.post("/auth/verify-email")
async def verify_email(req: VerifyEmailRequest):
    email = req.email.strip().lower()
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or verification code")
    if user.get("email_verified", True):
        raise HTTPException(status_code=400, detail="Email is already verified")
    if user.get("verification_expires_at", 0) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(status_code=400, detail="Verification code has expired")
    if not bcrypt.checkpw(req.code.encode(), user["verification_code_hash"].encode()):
        raise HTTPException(status_code=400, detail="Invalid email or verification code")

    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"verification_code_hash": "", "verification_expires_at": ""}},
    )
    return {
        "token": create_token(user["_id"]),
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "phone": user.get("phone", ""),
    }

@app.post("/auth/resend-verification")
async def resend_verification(req: ResendVerificationRequest):
    email = req.email.strip().lower()
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="No account was found for this email")
    if user.get("email_verified", True):
        raise HTTPException(status_code=400, detail="Email is already verified")

    verification_code = f"{secrets.randbelow(1000000):06d}"
    users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "verification_code_hash": bcrypt.hashpw(verification_code.encode(), bcrypt.gensalt()).decode(),
            "verification_expires_at": datetime.now(timezone.utc).timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60,
        }},
    )
    try:
        send_verification_email(email, verification_code)
    except Exception as error:
        logger.exception("Verification email resend failed for %s", email)
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"verification_required": True, "email": email}

@app.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    user = users.find_one({"email": email})
    if user:
        reset_code = f"{secrets.randbelow(1000000):06d}"
        users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "password_reset_code_hash": bcrypt.hashpw(reset_code.encode(), bcrypt.gensalt()).decode(),
                "password_reset_expires_at": datetime.now(timezone.utc).timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60,
            }},
        )
        try:
            send_verification_email(
                email,
                reset_code,
                subject="Reset your YouTube AI Assistant password",
                message_label="password reset",
            )
        except Exception as error:
            logger.exception("Password reset email failed for %s", email)
            raise HTTPException(status_code=502, detail=str(error)) from error
    return {"reset_required": True, "email": email}

@app.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    email = req.email.strip().lower()
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = users.find_one({"email": email})
    if not user or not user.get("password_reset_code_hash"):
        raise HTTPException(status_code=400, detail="Invalid or expired password reset code")
    if user.get("password_reset_expires_at", 0) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(status_code=400, detail="Password reset code has expired")
    if not bcrypt.checkpw(req.code.encode(), user["password_reset_code_hash"].encode()):
        raise HTTPException(status_code=400, detail="Invalid or expired password reset code")

    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()}, "$unset": {"password_reset_code_hash": "", "password_reset_expires_at": ""}},
    )
    return {"reset": True}

@app.post("/auth/login")
async def login(req: AuthRequest):
    email = req.email.strip().lower()
    user = users.find_one({"email": email})
    if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("email_verified", True):
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")
    return {
        "token": create_token(user["_id"]),
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "phone": user.get("phone", ""),
    }

@app.get("/auth/me")
async def me(user=Depends(current_user)):
    return {"email": user["email"], "full_name": user.get("full_name", ""), "phone": user.get("phone", "")}

@app.put("/auth/profile")
async def update_profile(req: ProfileUpdateRequest, user=Depends(current_user)):
    full_name = req.full_name.strip()
    phone = req.phone.strip()
    if not full_name or not phone:
        raise HTTPException(status_code=400, detail="Name and phone number are required")
    users.update_one({"_id": user["_id"]}, {"$set": {"full_name": full_name, "phone": phone}})
    return {"email": user["email"], "full_name": full_name, "phone": phone}

@app.get("/history")
async def get_history(user=Depends(current_user)):
    try:
        history = {}
        for message in messages.find(
            {"user": user["_id"]},
            {"_id": 0, "url": 1, "title": 1, "role": 1, "content": 1},
        ).sort("created_at", ASCENDING):
            url = message["url"]
            if url not in history:
                history[url] = {"title": message.get("title") or url, "messages": []}
            if message.get("title") and history[url]["title"] == url:
                history[url]["title"] = message["title"]
            history[url]["messages"].append({"role": message["role"], "content": message["content"]})

        return [{"url": url, **conversation} for url, conversation in history.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def normalize_video_url(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    if not text:
        return ""

    match = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", text)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return text.rstrip("/")

@app.delete("/history/{url}")
async def delete_history(url: str, user=Depends(current_user)):
    try:
        from urllib.parse import unquote
        decoded_url = unquote(url)
        normalized_target = normalize_video_url(decoded_url)

        delete_filter = {
            "user": user["_id"],
            "$or": [
                {"url": decoded_url},
                {"url": decoded_url.rstrip("/")},
                {"url": normalized_target},
                {"url": normalized_target.rstrip("/")},
            ],
        }

        result = messages.delete_many(delete_filter)
        return {"deleted": True, "url": decoded_url, "deleted_count": result.deleted_count}
    except Exception as error:
        logger.exception("Delete history failed for user %s and url %s", user.get("_id"), url)
        raise HTTPException(status_code=500, detail=str(error)) from error

@app.get("/transcript")
async def transcript(url: str, user=Depends(current_user)):
    try:
        title = url
        try:
            title_response = requests.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=5,
            )
            title_response.raise_for_status()
            title = title_response.json().get("title") or url
        except Exception:
            logger.warning("Could not fetch YouTube title for %s", url)
        return {"transcript_text": get_transcript(extract_video_id(url)), "title": title}
    except TranscriptUnavailableError as error:
        logger.warning("Transcript unavailable for %s: %s", url, error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("Transcript request failed for %s", url)
        raise HTTPException(status_code=500, detail=str(error)) from error

@app.post("/chat")
async def chat(req: QueryRequest, user=Depends(current_user)):
    stage = "load conversation history"
    try:
        # Fetch existing conversation history for this URL to provide memory
        previous_messages = messages.find(
            {"user": user["_id"], "url": req.url}, {"_id": 0, "role": 1, "content": 1}
        ).sort("created_at", -1).limit(6)
        history = [{"role": item["role"], "content": item["content"]} for item in previous_messages]
        history.reverse()

        # Save user question
        messages.insert_one({
            "user": user["_id"],
            "url": req.url,
            "title": req.video_title or req.url,
            "role": "user",
            "content": req.question,
            "created_at": datetime.now(timezone.utc),
        })
        
        # Get AI answer — pass full history for context memory
        stage = "generate AI answer"
        answer = answer_question(
            req.url,
            req.question,
            history,
            transcript_text=req.transcript_text,
        )
        
        # Save AI answer
        stage = "save AI answer"
        messages.insert_one({
            "user": user["_id"],
            "url": req.url,
            "title": req.video_title or req.url,
            "role": "assistant",
            "content": answer,
            "created_at": datetime.now(timezone.utc),
        })
        
        return {"answer": answer, "title": req.video_title or req.url}
    except TranscriptUnavailableError as error:
        logger.warning("Transcript unavailable for %s: %s", req.url, error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as e:
        logger.exception("Chat request failed during %s for video URL %s", stage, req.url)
        raise HTTPException(status_code=500, detail=str(e))
