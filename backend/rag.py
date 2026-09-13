import os
import re
from typing import List, Dict
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

_vector_cache: dict[str, FAISS] = {}


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
llm = ChatGroq(model=MODEL, temperature=0)

def answer_question(url: str, question: str, history: List[Dict] = None) -> str:
    """Return an answer for *question* about the YouTube video at *url*.
    Accepts an optional *history* list of {role, content} dicts to maintain
    conversation memory across multiple turns.
    The transcript and vector store are cached per video ID.
    """
    video_id = extract_video_id(url)

    # Reuse cached vector store if available
    if video_id in _vector_cache:
        vectorstore = _vector_cache[video_id]
    else:
        transcript = get_transcript(video_id)
        vectorstore = create_vector_store(transcript)
        _vector_cache[video_id] = vectorstore

    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    docs = retriever.invoke(question)
    context = "\n\n".join(doc.page_content for doc in docs)

    # Build LangChain message history from previous turns
    lc_history = []
    if history:
        for msg in history:
            if msg["role"] == "user":
                lc_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_history.append(AIMessage(content=msg["content"]))

    # Build the full message list: system + history + current question
    system_msg = SystemMessage(content=f"""You are a friendly and helpful YouTube AI assistant.
If the user greets you (e.g., "Hi", "Hello"), respond warmly and ask how you can help them with the video.

For video-related questions, answer using the transcript context below. 
Format responses using Markdown bullet points for lists, summaries, or step-by-step explanations.
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
    api = YouTubeTranscriptApi()

    try:
        # Direct fetch avoids the caption-list endpoint, which is more likely
        # to be blocked or fail on cloud server IPs.
        if hasattr(api, "fetch"):
            try:
                fetched = api.fetch(video_id, languages=("en", "hi", "mr"))
                return " ".join(
                    chunk["text"] if isinstance(chunk, dict) else chunk.text
                    for chunk in fetched
                )
            except Exception:
                pass

        if hasattr(api, "list"):
            transcript_list = api.list(video_id)
        else:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

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
        raise TranscriptUnavailableError(
            "YouTube captions could not be retrieved from this server. "
            "The video may have captions disabled, or YouTube may be blocking "
            "the EC2 server IP. Try another video or configure a proxy."
        ) from error

    return " ".join(
        chunk["text"] if isinstance(chunk, dict) else chunk.text
        for chunk in fetched
    )


# ----------------------------
# Vector Store
# ----------------------------

def create_vector_store(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=400,
    )

    docs = splitter.create_documents([text])

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return FAISS.from_documents(docs, embeddings)




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