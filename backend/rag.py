import os
import re
import logging
import hashlib
from typing import List, Dict
import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

_vector_cache: dict[str, FAISS] = {}
_transcript_hashes: dict[str, str] = {}
_embeddings = None
logger = logging.getLogger(__name__)


class TranscriptUnavailableError(RuntimeError):
    """Raised when YouTube does not provide captions to this server."""

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# Initialize LLM at module level for reuse
llm = ChatGroq(model=MODEL, temperature=0, max_tokens=1200)

def answer_question(
    url: str,
    question: str,
    history: List[Dict] = None,
    transcript_text: str | None = None,
) -> str:
    """Return an answer for *question* about the YouTube video at *url*.
    Accepts an optional *history* list of {role, content} dicts to maintain
    conversation memory across multiple turns.
    The transcript and vector store are cached per video ID.
    """
    video_id = extract_video_id(url)

    transcript_hash = hashlib.sha256(transcript_text.encode()).hexdigest() if transcript_text else None
    if video_id in _vector_cache and _transcript_hashes.get(video_id) == transcript_hash:
        vectorstore = _vector_cache[video_id]
    else:
        transcript = transcript_text or get_transcript(video_id)
        vectorstore = create_vector_store(transcript)
        _vector_cache[video_id] = vectorstore
        _transcript_hashes[video_id] = transcript_hash

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke(question)
    context = "\n\n".join(doc.page_content for doc in docs)[:7000]

    # Build LangChain message history from previous turns
    lc_history = []
    if history:
        for msg in history[-4:]:
            content = msg["content"][:1000]
            if msg["role"] == "user":
                lc_history.append(HumanMessage(content=content))
            elif msg["role"] == "assistant":
                lc_history.append(AIMessage(content=content))

    # Build the full message list: system + history + current question
    system_msg = SystemMessage(content=f"""You are a friendly and helpful YouTube AI assistant.
If the user greets you (e.g., "Hi", "Hello"), respond warmly and ask how you can help them with the video.

For video-related questions, answer using only the transcript context below when possible.
Keep answers concise and directly answer the question.
Use valid GitHub-Flavored Markdown:
- Use a Markdown table only for genuinely tabular data with consistent columns. Keep each cell short and never put a whole paragraph or code in a table.
- Use fenced code blocks with a language tag for source code, commands, JSON, SQL, or other code. Never place code in a Markdown table.
- Use bullet points for lists and short paragraphs for explanations.
- Close every fenced code block and keep table rows aligned with the header.
- Do not output raw HTML, extremely wide lines, or unnecessary repetition.
If the answer is not in the transcript, say you couldn't find it but offer helpful general knowledge if relevant.
You also have access to the previous conversation — use it to answer follow-up questions naturally.

Transcript Context:
{context}""")

    messages = [system_msg] + lc_history + [HumanMessage(content=question)]
    response = llm.invoke(messages)
    return response.content


# ----------------------------
# Extract Video ID
# ----------------------------

def extract_video_id(url):
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})",
        r"shorts/([0-9A-Za-z_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError("Invalid YouTube URL")


# ----------------------------
# Fetch Transcript
# ----------------------------

def get_transcript(video_id):
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if rapidapi_key:
        return get_rapidapi_transcript(video_id, rapidapi_key)

    proxy_url = os.getenv("YOUTUBE_PROXY")
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    cookies_path = os.getenv("YOUTUBE_COOKIES_FILE")
    if cookies_path and not os.path.isfile(cookies_path):
        raise TranscriptUnavailableError(
            f"YouTube cookies file was not found: {cookies_path}"
        )
    api = YouTubeTranscriptApi()

    try:
        # Version 0.6.x uses get_transcript and accepts requests proxies.
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            fetched = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=("en", "hi", "mr"),
                proxies=proxies,
                cookies=cookies_path,
            )
            return " ".join(chunk["text"] for chunk in fetched)

        # Direct fetch avoids the caption-list endpoint, which is more likely
        # to be blocked or fail on cloud server IPs.
        if hasattr(api, "fetch"):
            fetched = api.fetch(video_id, languages=("en", "hi", "mr"))
            return " ".join(
                chunk["text"] if isinstance(chunk, dict) else chunk.text
                for chunk in fetched
            )

        if hasattr(api, "list"):
            transcript_list = api.list(video_id)
        else:
            transcript_list = YouTubeTranscriptApi.list_transcripts(
                video_id,
                proxies=proxies,
                cookies=cookies_path,
            )

        try:
            transcript = transcript_list.find_manually_created_transcript(
                ["mr", "hi", "en"]
            )
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(
                    ["mr", "hi", "en"]
                )
            except Exception:
                transcript = next(iter(transcript_list))

        fetched = transcript.fetch()
    except Exception as error:
        logger.exception("YouTube transcript retrieval failed for video %s", video_id)
        raise TranscriptUnavailableError(
            "YouTube captions could not be retrieved from this server. "
            "The video may have captions disabled, or YouTube may be blocking "
            "the EC2 server IP. Try another video or configure a proxy."
        ) from error

    return " ".join(
        chunk["text"] if isinstance(chunk, dict) else chunk.text
        for chunk in fetched
    )


def get_rapidapi_transcript(video_id, rapidapi_key):
    """Fetch captions from the configured RapidAPI transcript provider."""
    endpoint = os.getenv("RAPIDAPI_TRANSCRIPT_URL")
    host = os.getenv("RAPIDAPI_HOST")
    parameter = os.getenv("RAPIDAPI_VIDEO_PARAMETER", "videoId")
    if not endpoint or not host:
        raise TranscriptUnavailableError(
            "RAPIDAPI_TRANSCRIPT_URL and RAPIDAPI_HOST must be configured"
        )

    try:
        response = requests.get(
            endpoint,
            params={parameter: video_id},
            headers={
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": host,
            },
            timeout=30,
        )
        response.raise_for_status()
        text = extract_transcript_text(response.json())
        if not text:
            raise ValueError("RapidAPI returned no transcript text")
        return text
    except Exception as error:
        logger.exception("RapidAPI transcript retrieval failed for video %s", video_id)
        raise TranscriptUnavailableError(
            "The configured RapidAPI transcript service could not return captions. "
            "Check its endpoint, host, API key, and quota."
        ) from error


def extract_transcript_text(payload):
    """Extract text from common RapidAPI transcript response shapes."""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        parts = [extract_transcript_text(item) for item in payload]
        return " ".join(part for part in parts if part)
    if isinstance(payload, dict):
        for key in ("text", "transcript", "captions", "data", "result", "items"):
            if key in payload:
                text = extract_transcript_text(payload[key])
                if text:
                    return text
    return ""


# ----------------------------
# Vector Store
# ----------------------------

def create_vector_store(text):
    global _embeddings
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=400,
    )

    docs = splitter.create_documents([text])

    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    return FAISS.from_documents(docs, _embeddings)




# ----------------------------
# Main
# ----------------------------

def main():

    url = input("Enter YouTube URL: ")

    video_id = extract_video_id(url)

    print("Fetching transcript...")

    transcript = get_transcript(video_id)

    print("Transcript Loaded.")

    print("Creating embeddings...")

    vectorstore = create_vector_store(transcript)

    retriever = vectorstore.as_retriever(
        search_kwargs={"k":10}
    )

    llm = ChatGroq(
        model=MODEL,
        temperature=0
    )

    print("\n===========================")
    print("YouTube AI Chat Started")
    print("Type 'exit' to quit.")
    print("===========================")

    while True:

        question = input("\nYou : ")

        if question.lower() == "exit":
            break

        docs = retriever.invoke(question)

        context = "\n\n".join(
            doc.page_content for doc in docs
        )

        messages = prompt.invoke(
            {
                "context": context,
                "question": question,
            }
        )

        response = llm.invoke(messages)

        print("\nAI:", response.content)


if __name__ == "__main__":
    main()