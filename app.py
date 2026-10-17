import streamlit as st

st.set_page_config(
    page_title="ResearchPilot | AI Knowledge Hub",
    page_icon="🧭",
    layout="wide"
)

# Define the 5 dedicated workspaces (removed view_report_page to reduce complexity)
home_page = st.Page("views/home.py", title="Dashboard", icon="🏠", default=True)
doc_page = st.Page("views/document_studio.py", title="Document & Book Studio", icon="📄")
web_page = st.Page("views/article_studio.py", title="Web Article Analyzer", icon="🌐")
yt_page = st.Page("views/youtube_studio.py", title="YouTube Video Hub", icon="🎥")
agent_page = st.Page("views/agent_workspace.py", title="Autonomous Research Agent", icon="🕵️")

pg = st.navigation({
    "Overview": [home_page],
    "Knowledge Studios": [doc_page, web_page, yt_page],
    "AI Power Tools": [agent_page]
})

# Global reading preferences in the sidebar
with st.sidebar:
    st.markdown("### 🎛️ Reading Preferences")
    st.session_state["style"] = st.selectbox(
        "Explanation Style",
        ["Academic", "Beginner Friendly", "Interview Preparation", "Technical"]
    )
    st.session_state["length"] = st.selectbox(
        "Detail Level",
        ["Short", "Medium", "Detailed"],
        index=1
    )
    st.caption("⚡ Powered by an automated multi-model waterfall & local CPU embeddings.")

# Run the navigation router
pg.run()