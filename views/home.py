import streamlit as st
import os
from supabase.client import Client, create_client
from langchain_community.vectorstores import SupabaseVectorStore
from core.engine import get_embeddings

# 1. CSS INJECTION (Glassmorphism, Mountain Night Gradient, Pills, Hover Lift)
st.markdown("""
    <style>
        /* Deep Mountain Night Gradient Background */
        .stApp {
            background: linear-gradient(180deg, #0A0F1A 0%, #111827 50%, #1F2937 100%);
            color: #E5E7EB;
        }
        /* Glassmorphism for Cards */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(17, 24, 39, 0.4) !important;
            backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        }
        /* Hover Lift Effect */
        [data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
            border-color: rgba(56, 189, 248, 0.4) !important;
        }
        /* Custom Pill Badges */
        .badge-Document { background-color: rgba(59, 130, 246, 0.2); color: #60A5FA; padding: 4px 10px; border-radius: 99px; font-size: 0.8rem; border: 1px solid rgba(59, 130, 246, 0.3); }
        .badge-Web { background-color: rgba(16, 185, 129, 0.2); color: #34D399; padding: 4px 10px; border-radius: 99px; font-size: 0.8rem; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-YouTube { background-color: rgba(239, 68, 68, 0.2); color: #F87171; padding: 4px 10px; border-radius: 99px; font-size: 0.8rem; border: 1px solid rgba(239, 68, 68, 0.3); }
    </style>
""", unsafe_allow_html=True)

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

st.title(":material/explore: ResearchPilot")
st.write("Transform dense books, research papers, web articles, and YouTube lectures into structured encyclopedic reports.")
st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    with st.container(border=True):
        st.subheader(":material/description: Document Studio")
        st.write("Upload PDFs, books, `.txt`, or `.md` files for deep structural synthesis.")
        if st.button("Open Document Studio", use_container_width=True, key="btn_doc", icon=":material/arrow_forward:"):
            st.switch_page("views/document_studio.py")

with col2:
    with st.container(border=True):
        st.subheader(":material/language: Web Article Studio")
        st.write("Analyze online blogs, documentation, news, or ArXiv HTML links.")
        if st.button("Open Article Studio", use_container_width=True, key="btn_web", icon=":material/arrow_forward:"):
            st.switch_page("views/article_studio.py")

with col3:
    with st.container(border=True):
        st.subheader(":material/smart_display: YouTube Hub")
        st.write("Watch lectures side-by-side with AI transcript synthesis.")
        if st.button("Open YouTube Hub", use_container_width=True, key="btn_yt", icon=":material/arrow_forward:"):
            st.switch_page("views/youtube_studio.py")

with col4:
    with st.container(border=True):
        st.subheader(":material/travel_explore: Research Agent")
        st.write("Autonomous multi-tool agent combining search and loaded files.")
        if st.button("Open Research Agent", use_container_width=True, key="btn_agent", icon=":material/arrow_forward:"):
            st.switch_page("views/agent_workspace.py")

st.divider()
st.subheader(":material/folder_open: Active Knowledge Library Vault")

response = supabase.table("saved_reports").select("*").order("created_at", desc=True).limit(12).execute()
db_reports = response.data

if not db_reports:
    st.info("Your knowledge library is currently empty. Head over to a studio to load your first source!")
else:
    for item in db_reports:
        with st.container(border=True):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f"### {item['title']}")
                time_formatted = item['created_at'][:10]
                badge_class = "badge-Document" if "Document" in item['source_type'] else "badge-Web" if "Web" in item['source_type'] else "badge-YouTube"
                
                # Render Pill Badge alongside the source info
                st.markdown(f"<span class='{badge_class}'>{item['source_type']}</span> &nbsp;&nbsp; **Source:** `{item['source_name']}` &nbsp;|&nbsp; **Analyzed:** {time_formatted}", unsafe_allow_html=True)

            with col_btn:
                st.write("") 
                if st.button("Open Studio", key=f"jump_{item['report_id']}", use_container_width=True, icon=":material/menu_book:"):
                    if "saved_reports" not in st.session_state:
                        st.session_state["saved_reports"] = {}
                    
                    vector_store = SupabaseVectorStore(client=supabase, embedding=get_embeddings(), table_name="documents", query_name="match_documents")
                    st.session_state["saved_reports"][item["report_id"]] = {
                        "report_id": item["report_id"], "title": item["title"], "type": item["source_type"],
                        "source_name": item["source_name"], "namespace": item["namespace"], "time": time_formatted,
                        "vector_store": vector_store, "result": item["result_json"], "chat": [], "quiz": None, "flashcards": None, "pptx_binary": None
                    }
                    st.session_state[f"{item['namespace']}_active_report"] = item["report_id"]
                    route_map = {"doc": "views/document_studio.py", "web": "views/article_studio.py", "yt": "views/youtube_studio.py"}
                    st.switch_page(route_map.get(item['namespace'], "views/document_studio.py"))

                if st.button("Delete", key=f"del_{item['report_id']}", use_container_width=True, icon=":material/delete_forever:"):
                    supabase.table("saved_reports").delete().eq("report_id", item['report_id']).execute()
                    supabase.table("documents").delete().eq("metadata->>report_id", item['report_id']).execute()
                    if "saved_reports" in st.session_state: st.session_state["saved_reports"].pop(item['report_id'], None)
                    if st.session_state.get(f"{item['namespace']}_active_report") == item['report_id']: st.session_state.pop(f"{item['namespace']}_active_report", None)
                    st.toast("Document permanently deleted from cloud vault!", icon=":material/delete:")
                    st.rerun()