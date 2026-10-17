import uuid
import os
import streamlit as st
from supabase.client import Client, create_client
from core.loaders import load_youtube_video, build_vector_index
from core.study_tools import run_initial_analysis, render_knowledge_workspace

# Initialize Supabase Client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

st.title("🎥 YouTube Video Knowledge Hub")
st.write("Paste any YouTube lecture, podcast, or tutorial URL to watch the video while generating structured notes, RAG Q&A, and quizzes.")
st.divider()

yt_url = st.text_input(
    "Enter YouTube Video URL:",
    placeholder="https://www.youtube.com/watch?v=..."
)

if st.button("🎥 Fetch Transcript & Analyze Video", type="primary"):
    if not yt_url or not yt_url.strip():
        st.warning("Please enter a YouTube URL.")
    else:
        source_name = yt_url.strip()
        
        # 1. DUPLICATE CHECK
        existing = supabase.table("saved_reports").select("report_id").eq("source_name", source_name).execute()
        if existing.data:
            st.warning(f"⚠️ The video **'{source_name}'** has already been analyzed and is saved in your vault! Please return to the Home dashboard to open it.")
            st.stop()

        # 2. IF NEW: Proceed with analysis
        try:
            with st.spinner("Fetching YouTube transcript and building cloud vector store..."):
                report_id = str(uuid.uuid4())[:8]
                chunks = load_youtube_video(source_name)
                
                # Stamp chunks with report_id for isolation and add unique ID
                for chunk in chunks:
                    chunk.metadata["report_id"] = report_id
                    if "id" not in chunk.metadata:
                        chunk.metadata["id"] = str(uuid.uuid4())
                        
                vector_store = build_vector_index(chunks)

            run_initial_analysis(
                report_id=report_id,
                vector_store=vector_store,
                chunk_count=len(chunks),
                style=st.session_state.get("style", "Academic"),
                length=st.session_state.get("length", "Medium"),
                source_label="YouTube Video",
                source_name=source_name,
                namespace="yt"
            )
            st.success(f"Indexed **{len(chunks)}** transcript segments from YouTube!")
        except Exception as e:
            st.error(f"Could not load YouTube transcript (make sure the video has English/Hindi captions enabled): {e}")

if yt_url.strip():
    with st.expander("▶️ Watch YouTube Video Player", expanded=False):
        st.video(yt_url.strip())

render_knowledge_workspace(namespace="yt")