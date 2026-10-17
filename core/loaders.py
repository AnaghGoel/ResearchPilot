import os
import re
import tempfile
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase.client import Client, create_client

from core.engine import get_embeddings
import uuid

load_dotenv()

# Initialize Supabase Client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)

def build_vector_index(chunks: list[Document]) -> SupabaseVectorStore:
    """Embeds chunks and saves them permanently to the Supabase 'documents' table with unique IDs."""
    embeddings = get_embeddings()
    
    # Ensure every chunk has a unique id in metadata so Supabase doesn't throw a null constraint error
    for chunk in chunks:
        if "id" not in chunk.metadata:
            chunk.metadata["id"] = str(uuid.uuid4())
            
    return SupabaseVectorStore.from_documents(
        chunks,
        embeddings,
        client=supabase,
        table_name="documents",
        query_name="match_documents"
    )

def load_uploaded_file(uploaded_file) -> list[Document]:
    filename = uploaded_file.name
    all_docs = []
    
    if filename.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        try:
            docs = PyPDFLoader(tmp_path).load()
            for d in docs:
                d.metadata["source"] = filename
            all_docs.extend(docs)
        finally:
            os.remove(tmp_path)
    else:
        text_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        all_docs.append(Document(page_content=text_content, metadata={"source": filename, "page": 1}))

    # Split documents and filter out empty text chunks
    split_chunks = splitter.split_documents(all_docs)
    return [chunk for chunk in split_chunks if chunk.page_content and chunk.page_content.strip()]

def load_web_article(url: str) -> list[Document]:
    docs = WebBaseLoader(url).load()
    for d in docs:
        d.metadata["source"] = url
    split_chunks = splitter.split_documents(docs)
    return [chunk for chunk in split_chunks if chunk.page_content and chunk.page_content.strip()]

def extract_youtube_id(url: str) -> Optional[str]:
    pattern = r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None

def load_youtube_video(url: str) -> list[Document]:
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL.")

    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.fetch(video_id, languages=["en", "hi"])
    full_text = " ".join([snippet.text for snippet in transcript_list])

    doc = Document(
        page_content=full_text,
        metadata={"source": f"YouTube ({video_id})", "video_id": video_id}
    )
    split_chunks = splitter.split_documents([doc])
    return [chunk for chunk in split_chunks if chunk.page_content and chunk.page_content.strip()]

def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(
        f"\n{d.page_content}"
        for d in docs
    )