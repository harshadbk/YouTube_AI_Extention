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
   - Fill in `OPENAI_API_KEY`, `GROQ_API_KEY`, `JWT_SECRET`, and your MongoDB Atlas `MONGODB_URI`.
   - Set `SENDGRID_API_KEY` to a server-side SendGrid API key and `SENDGRID_FROM_EMAIL` to a verified sender address. The default sender is `khataleharshad78@gmail.com`.
   - For Google sign-in, create a Web OAuth client in Google Cloud Console and set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and `FRONTEND_URL`.
   - Add the exact value of `GOOGLE_REDIRECT_URI` to the OAuth client's authorized redirect URIs.

Chat history is stored in the configured MongoDB database (`youtube_ai_extension` by
default). The connection string is read from `MONGODB_URI`; it is never stored in
source code.

If YouTube blocks transcript requests from the EC2 public IP, set
`YOUTUBE_PROXY` in `.env` to an HTTP or HTTPS proxy URL. The transcript client
uses that proxy for both HTTP and HTTPS requests.

To use a RapidAPI transcript provider instead, configure `RAPIDAPI_KEY`,
`RAPIDAPI_HOST`, and `RAPIDAPI_TRANSCRIPT_URL` in `.env`. The endpoint must
accept the video ID using the parameter named by `RAPIDAPI_VIDEO_PARAMETER`
(default: `videoId`). RapidAPI is used automatically when `RAPIDAPI_KEY` is set.

Authentication creates a `users` collection with hashed passwords. Registration
sends a six-digit verification code through SendGrid; call `POST /auth/verify-email`
with the email and code to receive a bearer token. Verified users can then use
`POST /auth/login`. Send the token with `GET /history` and `POST /chat`; messages
are stored with the user's ID in the `user` field and are isolated per account.
Google sign-in is available at `GET /auth/google/login` and uses the same bearer
token session after Google confirms the account email.

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Endpoints
- `GET /`: Health check
- `POST /upload`: Extract transcript and build RAG vector store for a video.
- `POST /chat`: Ask questions based on the uploaded video context.
