import os
import sys
import logging
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
from rag import TranscriptUnavailableError, answer_question

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

def create_token(user_id: str):
    return jwt.encode({"sub": user_id}, JWT_SECRET, algorithm="HS256")

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
    user = {
        "_id": user_id,
        "email": email,
        "full_name": full_name,
        "phone": phone,
        "password_hash": bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode(),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        users.insert_one(user)
    except Exception as error:
        if getattr(error, "code", None) == 11000:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise
    return {"token": create_token(user_id), "email": email, "full_name": full_name, "phone": phone}

@app.post("/auth/login")
async def login(req: AuthRequest):
    email = req.email.strip().lower()
    user = users.find_one({"email": email})
    if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "token": create_token(user["_id"]),
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "phone": user.get("phone", ""),
    }

@app.get("/auth/me")
async def me(user=Depends(current_user)):
    return {"email": user["email"], "full_name": user.get("full_name", ""), "phone": user.get("phone", "")}

@app.get("/history")
async def get_history(user=Depends(current_user)):
    try:
        history = {}
        for message in messages.find({"user": user["_id"]}, {"_id": 0, "url": 1, "role": 1, "content": 1}).sort("created_at", ASCENDING):
            url = message["url"]
            if url not in history:
                history[url] = []
            history[url].append({"role": message["role"], "content": message["content"]})

        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QueryRequest(BaseModel):
    url: str
    question: str

@app.post("/chat")
async def chat(req: QueryRequest, user=Depends(current_user)):
    stage = "load conversation history"
    try:
        # Fetch existing conversation history for this URL to provide memory
        previous_messages = messages.find(
            {"user": user["_id"], "url": req.url}, {"_id": 0, "role": 1, "content": 1}
        ).sort("created_at", ASCENDING)
        history = [{"role": item["role"], "content": item["content"]} for item in previous_messages]

        # Save user question
        messages.insert_one({
            "user": user["_id"],
            "url": req.url,
            "role": "user",
            "content": req.question,
            "created_at": datetime.now(timezone.utc),
        })
        
        # Get AI answer — pass full history for context memory
        stage = "generate AI answer"
        answer = answer_question(req.url, req.question, history)
        
        # Save AI answer
        stage = "save AI answer"
        messages.insert_one({
            "user": user["_id"],
            "url": req.url,
            "role": "assistant",
            "content": answer,
            "created_at": datetime.now(timezone.utc),
        })
        
        return {"answer": answer}
    except TranscriptUnavailableError as error:
        logger.warning("Transcript unavailable for %s: %s", req.url, error)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as e:
        logger.exception("Chat request failed during %s for video URL %s", stage, req.url)
        raise HTTPException(status_code=500, detail=str(e))
