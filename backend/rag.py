import os
import re
import logging
import hashlib
from typing import List, Dict

import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ============================================================
# Configuration
# ============================================================

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

os.environ["GROQ_API_KEY"] = GROQ_API_KEY


# ============================================================
# Logging
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# Cache
# ============================================================

_vector_cache = {}
_transcript_hashes: dict[str, str] = {}


# ============================================================
# Exception
# ============================================================

class TranscriptUnavailableError(RuntimeError):
    """
    Raised when YouTube does not provide captions
    to this server.
    """
    pass


# ============================================================
# Groq LLM
# ============================================================

llm = ChatGroq(
    model=MODEL,
    temperature=0,
    max_tokens=1200
)


# ============================================================
# Local lexical retrieval
# ============================================================

class LexicalRetriever:
    def __init__(self, documents, k=3):
        self.documents = documents
        self.k = k

    @staticmethod
    def _terms(text):
        return set(re.findall(r"[a-z0-9]{2,}", text.lower()))

    def invoke(self, query):
        query_terms = self._terms(query)
        if not query_terms:
            return self.documents[:self.k]

        ranked = []
        for position, document in enumerate(self.documents):
            document_terms = self._terms(document.page_content)
            score = len(query_terms & document_terms)
            if score:
                ranked.append((score, -position, document))

        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [item[2] for item in ranked[:self.k]] or self.documents[:self.k]


class LexicalDocumentStore:
    def __init__(self, documents):
        self.documents = documents

    def as_retriever(self, search_kwargs=None):
        k = (search_kwargs or {}).get("k", 3)
        return LexicalRetriever(self.documents, k=k)


# ============================================================
# Answer Question
# ============================================================

def answer_question(
    url: str,
    question: str,
    history: List[Dict] = None,
    transcript_text: str | None = None,
) -> str:

    """
    Return an answer for a question about
    a YouTube video.
    """

    video_id = extract_video_id(url)

    transcript_hash = (
        hashlib.sha256(
            transcript_text.encode()
        ).hexdigest()
        if transcript_text
        else None
    )

    # --------------------------------------------------------
    # Check vector cache
    # --------------------------------------------------------

    if (
        video_id in _vector_cache
        and
        _transcript_hashes.get(video_id)
        == transcript_hash
    ):

        vectorstore = _vector_cache[video_id]

    else:

        transcript = (
            transcript_text
            or get_transcript(video_id)
        )

        vectorstore = create_vector_store(
            transcript
        )

        _vector_cache[video_id] = vectorstore

        _transcript_hashes[video_id] = (
            transcript_hash
        )

    # --------------------------------------------------------
    # Retriever
    # --------------------------------------------------------

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 3
        }
    )

    docs = retriever.invoke(question)

    context = "\n\n".join(
        doc.page_content
        for doc in docs
    )[:7000]

    # --------------------------------------------------------
    # Conversation history
    # --------------------------------------------------------

    lc_history = []

    if history:

        for msg in history[-4:]:

            content = msg.get(
                "content",
                ""
            )[:1000]

            if msg.get("role") == "user":

                lc_history.append(
                    HumanMessage(
                        content=content
                    )
                )

            elif msg.get("role") == "assistant":

                lc_history.append(
                    AIMessage(
                        content=content
                    )
                )

    # --------------------------------------------------------
    # System message
    # --------------------------------------------------------

    system_msg = SystemMessage(
        content=f"""
You are a friendly and helpful YouTube AI assistant.

If the user greets you such as:
Hi, Hello, Hey

respond warmly and ask how you can help them with the video.

For video-related questions:

Answer using the transcript context below whenever possible.

Keep answers concise and directly answer the question.

Use valid GitHub-Flavored Markdown.

Rules:

- Use a Markdown table only for genuinely tabular data.
- Keep table cells short.
- Never put code inside a Markdown table.
- Use fenced code blocks for source code, commands, JSON, and SQL.
- Use bullet points for lists.
- Use short paragraphs for explanations.
- Close every fenced code block.
- Do not output raw HTML.
- Avoid unnecessary repetition.

If the answer cannot be found in the transcript:

Say that you couldn't find it in the transcript.

You may provide helpful general knowledge if relevant.

You also have access to previous conversation history.
Use it naturally for follow-up questions.

--------------------------------------------------
TRANSCRIPT CONTEXT
--------------------------------------------------

{context}
"""
    )

    # --------------------------------------------------------
    # Messages
    # --------------------------------------------------------

    messages = (
        [system_msg]
        + lc_history
        + [
            HumanMessage(
                content=question
            )
        ]
    )

    # --------------------------------------------------------
    # Groq
    # --------------------------------------------------------

    response = llm.invoke(messages)

    return response.content


# ============================================================
# Extract YouTube Video ID
# ============================================================

def extract_video_id(url):

    patterns = [

        r"(?:v=)([0-9A-Za-z_-]{11})",

        r"youtu\.be/([0-9A-Za-z_-]{11})",

        r"embed/([0-9A-Za-z_-]{11})",

        r"shorts/([0-9A-Za-z_-]{11})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:

            return match.group(1)

    raise ValueError(
        "Invalid YouTube URL"
    )


# ============================================================
# Get YouTube Transcript
# ============================================================

def get_transcript(video_id):

    rapidapi_key = os.getenv(
        "RAPIDAPI_KEY"
    )

    if rapidapi_key:

        return get_rapidapi_transcript(
            video_id,
            rapidapi_key
        )

    proxy_url = os.getenv(
        "YOUTUBE_PROXY"
    )

    proxies = (
        {
            "http": proxy_url,
            "https": proxy_url
        }
        if proxy_url
        else None
    )

    cookies_path = os.getenv(
        "YOUTUBE_COOKIES_FILE"
    )

    if (
        cookies_path
        and
        not os.path.isfile(cookies_path)
    ):

        raise TranscriptUnavailableError(
            f"YouTube cookies file was not found: "
            f"{cookies_path}"
        )

    api = YouTubeTranscriptApi()

    try:

        # ----------------------------------------------------
        # Older youtube-transcript-api
        # ----------------------------------------------------

        if hasattr(
            YouTubeTranscriptApi,
            "get_transcript"
        ):

            fetched = (
                YouTubeTranscriptApi
                .get_transcript(
                    video_id,
                    languages=(
                        "en",
                        "hi",
                        "mr"
                    ),
                    proxies=proxies,
                    cookies=cookies_path
                )
            )

            return " ".join(
                chunk["text"]
                for chunk in fetched
            )

        # ----------------------------------------------------
        # Newer API
        # ----------------------------------------------------

        if hasattr(api, "fetch"):

            fetched = api.fetch(
                video_id,
                languages=(
                    "en",
                    "hi",
                    "mr"
                )
            )

            return " ".join(

                chunk["text"]
                if isinstance(
                    chunk,
                    dict
                )
                else chunk.text

                for chunk in fetched
            )

        # ----------------------------------------------------
        # Transcript list
        # ----------------------------------------------------

        if hasattr(api, "list"):

            transcript_list = api.list(
                video_id
            )

        else:

            transcript_list = (
                YouTubeTranscriptApi
                .list_transcripts(
                    video_id,
                    proxies=proxies,
                    cookies=cookies_path
                )
            )

        # ----------------------------------------------------
        # Manually created
        # ----------------------------------------------------

        try:

            transcript = (
                transcript_list
                .find_manually_created_transcript(
                    [
                        "mr",
                        "hi",
                        "en"
                    ]
                )
            )

        except Exception:

            try:

                transcript = (
                    transcript_list
                    .find_generated_transcript(
                        [
                            "mr",
                            "hi",
                            "en"
                        ]
                    )
                )

            except Exception:

                transcript = next(
                    iter(transcript_list)
                )

        fetched = transcript.fetch()

    except Exception as error:

        logger.exception(
            "YouTube transcript retrieval failed "
            "for video %s",
            video_id
        )

        raise TranscriptUnavailableError(
            "YouTube captions could not be retrieved "
            "from this server. "
            "The video may have captions disabled, "
            "or YouTube may be blocking the EC2 "
            "server IP. "
            "Try another video or configure a proxy."
        ) from error

    return " ".join(

        chunk["text"]
        if isinstance(
            chunk,
            dict
        )
        else chunk.text

        for chunk in fetched
    )


# ============================================================
# RapidAPI Transcript
# ============================================================

def get_rapidapi_transcript(
    video_id,
    rapidapi_key
):

    endpoint = os.getenv(
        "RAPIDAPI_TRANSCRIPT_URL"
    )

    host = os.getenv(
        "RAPIDAPI_HOST"
    )

    parameter = os.getenv(
        "RAPIDAPI_VIDEO_PARAMETER",
        "videoId"
    )

    if not endpoint or not host:

        raise TranscriptUnavailableError(
            "RAPIDAPI_TRANSCRIPT_URL and "
            "RAPIDAPI_HOST must be configured"
        )

    try:

        response = requests.get(

            endpoint,

            params={
                parameter: video_id
            },

            headers={

                "x-rapidapi-key":
                    rapidapi_key,

                "x-rapidapi-host":
                    host
            },

            timeout=30
        )

        response.raise_for_status()

        text = extract_transcript_text(
            response.json()
        )

        if not text:

            raise ValueError(
                "RapidAPI returned no transcript text"
            )

        return text

    except Exception as error:

        logger.exception(
            "RapidAPI transcript retrieval failed "
            "for video %s",
            video_id
        )

        raise TranscriptUnavailableError(
            "The configured RapidAPI transcript "
            "service could not return captions. "
            "Check its endpoint, host, API key, "
            "and quota."
        ) from error


# ============================================================
# Extract Transcript Text
# ============================================================

def extract_transcript_text(payload):

    if isinstance(
        payload,
        str
    ):

        return payload.strip()

    if isinstance(
        payload,
        list
    ):

        parts = [

            extract_transcript_text(
                item
            )

            for item in payload
        ]

        return " ".join(
            part
            for part in parts
            if part
        )

    if isinstance(
        payload,
        dict
    ):

        for key in (
            "text",
            "transcript",
            "captions",
            "data",
            "result",
            "items"
        ):

            if key in payload:

                text = (
                    extract_transcript_text(
                        payload[key]
                    )
                )

                if text:

                    return text

    return ""


# ============================================================
# Create Vector Store
# ============================================================

def create_vector_store(text):

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=2000,

        chunk_overlap=400
    )

    docs = splitter.create_documents(
        [text]
    )

    return LexicalDocumentStore(docs)


# ============================================================
# Command Line Main
# ============================================================

def main():

    url = input(
        "Enter YouTube URL: "
    )

    video_id = extract_video_id(
        url
    )

    print(
        "Fetching transcript..."
    )

    transcript = get_transcript(
        video_id
    )

    print(
        "Transcript Loaded."
    )

    print(
        "Creating embeddings..."
    )

    vectorstore = create_vector_store(
        transcript
    )

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 10
        }
    )

    print(
        "\n==========================="
    )

    print(
        "YouTube AI Chat Started"
    )

    print(
        "Type 'exit' to quit."
    )

    print(
        "==========================="
    )

    # --------------------------------------------------------
    # Chat loop
    # --------------------------------------------------------

    while True:

        question = input(
            "\nYou : "
        )

        if question.lower() == "exit":

            break

        docs = retriever.invoke(
            question
        )

        context = "\n\n".join(

            doc.page_content

            for doc in docs
        )

        prompt = ChatPromptTemplate.from_messages(

            [

                (
                    "system",

                    """
You are a helpful YouTube AI assistant.

Answer the user's question using
the provided transcript context.

If the answer is not present,
say that it was not found in
the transcript.

Keep the answer concise.

Transcript context:

{context}
"""
                ),

                (
                    "human",
                    "{question}"
                )
            ]
        )

        messages = prompt.invoke(

            {
                "context": context,

                "question": question
            }
        )

        response = llm.invoke(
            messages
        )

        print(
            "\nAI:",
            response.content
        )


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    main()