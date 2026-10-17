import uuid
import os
import streamlit as st
from supabase.client import Client, create_client
from core.loaders import load_web_article, build_vector_index
from core.study_tools import run_initial_analysis, render_knowledge_workspace

# Initialize Supabase Client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

st.title("🌐 Web Article & Documentation Analyzer")
st.write("Paste any blog post, technical documentation, encyclopedic page, or ArXiv HTML URL to extract structured insights.")
st.divider()

url_input = st.text_input(
    "Enter Web Article URL:",
    placeholder="https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
)

if st.button("🌐 Scrape & Analyze Article", type="primary"):
    if not url_input or not url_input.strip().startswith("http"):
        st.warning("Please enter a valid URL starting with http:// or https://")
    else:
        source_name = url_input.strip()
        
        # 1. DUPLICATE CHECK
        existing = supabase.table("saved_reports").select("report_id").eq("source_name", source_name).execute()
        if existing.data:
            st.warning(f"⚠️ The article **'{source_name}'** has already been analyzed and is saved in your vault! Please return to the Home dashboard to open it.")
            st.stop()

        # 2. IF NEW: Proceed with analysis
        try:
            with st.spinner("Scraping webpage and building cloud vector store..."):
                report_id = str(uuid.uuid4())[:8]
                chunks = load_web_article(source_name)
                
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
                source_label="Web Article",
                source_name=source_name,
                namespace="web"
            )
            st.success(f"Extracted and indexed **{len(chunks)}** chunks from the article!")
        except Exception as e:
            st.error(f"Could not scrape or analyze the URL: {e}")

render_knowledge_workspace(namespace="web")