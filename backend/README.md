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
   - Fill in `OPENAI_API_KEY`, `GROQ_API_KEY`, and your MongoDB Atlas `MONGODB_URI`.

Chat history is stored in the configured MongoDB database (`youtube_ai_extension` by
default). The connection string is read from `MONGODB_URI`; it is never stored in
source code.

If YouTube blocks transcript requests from the EC2 public IP, set
`YOUTUBE_PROXY` in `.env` to an HTTP or HTTPS proxy URL. The transcript client
uses that proxy for both HTTP and HTTPS requests.

Authentication creates a `users` collection with hashed passwords. Use
`POST /auth/register` or `POST /auth/login` to receive a bearer token. Send that
token with `GET /history` and `POST /chat`; messages are stored with the user's ID
in the `user` field and are isolated per account.

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Endpoints
- `GET /`: Health check
- `POST /upload`: Extract transcript and build RAG vector store for a video.
- `POST /chat`: Ask questions based on the uploaded video context.
