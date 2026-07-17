# FastAPI YouTube RAG Backend

This is a production-ready FastAPI backend for an AI-powered YouTube Chat application using Retrieval-Augmented Generation (RAG).

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   - Copy `.env.example` to `.env`
   - Fill in your `OPENAI_API_KEY` and `GROQ_API_KEY`.

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Endpoints
- `GET /`: Health check
- `POST /upload`: Extract transcript and build RAG vector store for a video.
- `POST /chat`: Ask questions based on the uploaded video context.
