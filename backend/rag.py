import os
import re
from dotenv import load_dotenv

from youtube_transcript_api import YouTubeTranscriptApi

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# ---------------------------------
# Load Environment Variables
# ---------------------------------

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv("GROQ_MODEL")

# ---------------------------------
# Extract Video ID
# ---------------------------------

def extract_video_id(url):

    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11})"

    match = re.search(pattern, url)

    if match:
        return match.group(1)

    raise ValueError("Invalid YouTube URL")

# ---------------------------------
# Fetch Transcript
# ---------------------------------

def get_transcript(video_id):

    ytt = YouTubeTranscriptApi()

    transcript_list = ytt.list(video_id)

    try:
        transcript = transcript_list.find_manually_created_transcript(
            ["mr", "hi", "en"]
        )

    except:

        try:
            transcript = transcript_list.find_generated_transcript(
                ["mr", "hi", "en"]
            )

        except:
            transcript = next(iter(transcript_list))

    fetched = transcript.fetch()

    transcript_text = " ".join(chunk.text for chunk in fetched)

    return transcript_text

# ---------------------------------
# Create Vector Store
# ---------------------------------

def create_vector_store(text):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    docs = splitter.create_documents([text])

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    vectorstore = FAISS.from_documents(
        docs,
        embeddings
    )

    return vectorstore

# ---------------------------------
# Prompt
# ---------------------------------

prompt = PromptTemplate(
    template="""
You are an AI assistant that answers questions ONLY using the provided YouTube transcript.

Rules:
1. Answer ONLY from the transcript context.
2. Do not make up facts.
3. If the answer is not available, reply:
   "I couldn't find that information in the video."
4. Reply in the SAME language as the user's question.
   - English → English
   - Hindi → Hindi
   - Marathi → Marathi
5. Keep answers clear and concise.
6. If appropriate, summarize information from multiple transcript sections.

Transcript:
{context}

Question:
{question}

Answer:
""",
    input_variables=["context", "question"],
)

# ---------------------------------
# Main
# ---------------------------------

def main():

    url = input("Enter YouTube URL: ")

    print("\nExtracting Video ID...")

    video_id = extract_video_id(url)

    print("Fetching Transcript...")

    transcript = get_transcript(video_id)

    print("Transcript Loaded Successfully!")

    print("Creating Vector Database...")

    vectorstore = create_vector_store(transcript)

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 4}
    )

    llm = ChatGroq(
        model=GROQ_MODEL,
        temperature=0
    )

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={
            "prompt": prompt
        },
        return_source_documents=True
    )

    print("\n======================================")
    print("YouTube AI Chat Started")
    print("Type 'exit' to quit.")
    print("======================================")

    while True:

        query = input("\nYou : ")

        if query.lower() in ["exit", "quit"]:
            break

        response = qa.invoke({"query": query})

        print("\nAI :", response["result"])


if __name__ == "__main__":
    main()