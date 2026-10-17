import uuid
import os
import streamlit as st
from supabase.client import Client, create_client
from langchain_core.documents import Document
from core.loaders import load_uploaded_file, build_vector_index, splitter
from core.study_tools import run_initial_analysis, render_knowledge_workspace

# Ensure CSS from home.py is active here too if this page is loaded directly
st.markdown("""
    <style>
        .stApp { background: linear-gradient(180deg, #0A0F1A 0%, #111827 50%, #1F2937 100%); color: #E5E7EB; }
        [data-testid="stFileUploadDropzone"] { display: none !important; } /* Hide upload box after file is chosen */
    </style>
""", unsafe_allow_html=True)

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

st.title(":material/description: Document Studio")
st.write("Upload a PDF, book, lecture note (`.txt`, `.md`), or paste text to build an interactive knowledge report.")
st.divider()

mode = st.radio("Select Input Type:", ["Upload File", "Paste Raw Text"], horizontal=True)

uploaded_file = None
raw_text = None

if mode == "Upload File":
    uploaded_file = st.file_uploader("Upload Document", type=["pdf", "txt", "md"], accept_multiple_files=False, key="single_upload_clean")
else:
    raw_text = st.text_area("Paste your text or book chapter here:", height=220)

if st.button("Analyze Document", type="primary", icon=":material/search_insights:"):
    if mode == "Upload File" and not uploaded_file:
        st.toast("Please upload a file first.", icon=":material/warning:")
    elif mode == "Paste Raw Text" and (not raw_text or not raw_text.strip()):
        st.toast("Please paste some text.", icon=":material/warning:")
    else:
        source_name = uploaded_file.name if mode == "Upload File" else "Pasted Text"
        
        existing = supabase.table("saved_reports").select("report_id").eq("source_name", source_name).execute()
        if existing.data:
            st.warning(f"⚠️ **'{source_name}'** has already been analyzed! Please return to the Home dashboard to open it.", icon=":material/info:")
            st.stop()

        try:
            with st.spinner("Splitting document and building cloud vector store..."):
                report_id = str(uuid.uuid4())[:8]
                chunks = load_uploaded_file(uploaded_file) if mode == "Upload File" else splitter.split_documents([Document(page_content=raw_text, metadata={"source": "Pasted Text", "page": 1})])
                for chunk in chunks:
                    chunk.metadata["report_id"] = report_id
                    if "id" not in chunk.metadata: chunk.metadata["id"] = str(uuid.uuid4())
                vector_store = build_vector_index(chunks)

            run_initial_analysis(
                report_id=report_id, vector_store=vector_store, chunk_count=len(chunks),
                style=st.session_state.get("style", "Academic"), length=st.session_state.get("length", "Medium"),
                source_label="Document", source_name=source_name, namespace="doc"
            )
            
        except Exception as e:
            st.error(f"Error processing document: {e}")

render_knowledge_workspace(namespace="doc")