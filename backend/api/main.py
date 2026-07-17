import os
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict

# Load environment variables
load_dotenv()

# Import RAG utilities
from rag import answer_question

app = FastAPI()

# Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "chats.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT url, role, content FROM messages ORDER BY id ASC")
        rows = cursor.fetchall()
        
        history = {}
        for row in rows:
            url, role, content = row
            if url not in history:
                history[url] = []
            history[url].append({"role": role, "content": content})
            
        conn.close()
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QueryRequest(BaseModel):
    url: str
    question: str

@app.post("/chat")
async def chat(req: QueryRequest):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Fetch existing conversation history for this URL to provide memory
        cursor.execute("SELECT role, content FROM messages WHERE url = ? ORDER BY id ASC", (req.url,))
        history = [{"role": r, "content": c} for r, c in cursor.fetchall()]

        # Save user question
        cursor.execute("INSERT INTO messages (url, role, content) VALUES (?, ?, ?)", (req.url, "user", req.question))
        conn.commit()
        
        # Get AI answer — pass full history for context memory
        answer = answer_question(req.url, req.question, history)
        
        # Save AI answer
        cursor.execute("INSERT INTO messages (url, role, content) VALUES (?, ?, ?)", (req.url, "assistant", answer))
        conn.commit()
        conn.close()
        
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
