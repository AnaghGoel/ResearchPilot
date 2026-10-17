import os
import streamlit as st
import arxiv
import wikipedia
from ddgs import DDGS
from supabase.client import Client, create_client

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_community.vectorstores import SupabaseVectorStore

from core.engine import get_waterfall_llm, get_embeddings
from core.loaders import format_docs
from core.study_tools import get_smart_retriever

wikipedia.set_user_agent("ResearchPilot/2.0 (https://github.com/AnaghGoel/ResearchPilot)")

st.title(":material/travel_explore: Autonomous Multi-Tool Agent")
st.write("Ask complex questions across all your saved reports in the library vault, combined with live DuckDuckGo Web Search, ArXiv Papers, and Wikipedia.")
st.divider()

@tool
def list_active_vault_documents() -> str:
    """
    Use this tool FIRST when the user asks to classify, list, or summarize the documents, articles, or videos in their vault.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    response = supabase.table("saved_reports").select("title, source_type, source_name").execute()
    db_reports = response.data
    
    if not db_reports:
        return "The vault is completely empty."
        
    doc_list = [f"- Title: {item['title']} | Type: {item['source_type']} | Source: {item['source_name']}" for item in db_reports]
    return "Here are the documents currently in the user's vault:\n" + "\n".join(doc_list)

@tool
def search_loaded_knowledge_base(query: str) -> str:
    """Search for specific information inside all user-loaded PDFs, Web Articles, and YouTube transcripts saved in the cloud database."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    vector_store = SupabaseVectorStore(
        client=supabase,
        embedding=get_embeddings(),
        table_name="documents",
        query_name="match_documents"
    )
    
    retriever, _ = get_smart_retriever(vector_store, total_chunks=50, query=query, mode="qa")
    docs = retriever.invoke(query)
    
    if not docs:
        return "No relevant context found in the saved reports for this query."
        
    results = []
    for d in docs:
        source = d.metadata.get("source", "Unknown Source")
        page = d.metadata.get("page", "N/A")
        results.append(f"\n{d.page_content}")
        
    return "\n\n---\n\n".join(results)

@tool
def search_web(query: str) -> str:
    """Search the live internet using DuckDuckGo for companies, startups, current news, or topics not found on Wikipedia."""
    try:
        results = DDGS().text(query, max_results=4)
        if not results:
            return f"No web results found for '{query}'."
        return "\n\n---\n\n".join(
            f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nURL: {r.get('href')}"
            for r in results
        )
    except Exception as e:
        return f"Web search error: {e}"

@tool
def search_arxiv(query: str) -> str:
    """Search the live ArXiv database for academic research papers, titles, authors, and abstracts."""
    try:
        client = arxiv.Client()
        clean_query = query.replace('"', '').strip()
        search = arxiv.Search(query=clean_query, max_results=3, sort_by=arxiv.SortCriterion.Relevance)
        results = list(client.results(search))
        if not results:
            return f"No ArXiv papers found for '{clean_query}'."
        return "\n\n---\n\n".join(
            f"Title: {p.title}\nPublished: {p.published.strftime('%Y-%m-%d')}\n"
            f"Authors: {', '.join(a.name for a in p.authors[:4])}\nSummary: {p.summary[:700]}...\nURL: {p.entry_id}"
            for p in results
        )
    except Exception as e:
        return f"ArXiv search error: {e}"

@tool
def search_wikipedia(query: str) -> str:
    """Search Wikipedia ONLY for established encyclopedic concepts, scientific definitions, or historical topics."""
    try:
        clean_query = query.replace('"', '').strip()
        titles = wikipedia.search(clean_query, results=3)
        if not titles:
            return f"No Wikipedia articles found for '{clean_query}'. Use `search_web` instead."
        summaries = []
        for t in titles:
            try:
                page = wikipedia.page(t, auto_suggest=False)
                summaries.append(f"Page: {page.title}\nSummary: {page.summary[:600]}...")
            except wikipedia.DisambiguationError as e:
                summaries.append(f"'{t}' is ambiguous (Options: {', '.join(e.options[:5])}). Use `search_web` for specific companies.")
            except Exception:
                continue
        return "\n\n".join(summaries) if summaries else f"No exact Wikipedia match. Use `search_web`."
    except Exception as e:
        return f"Wikipedia search error: {e}"

tools = [list_active_vault_documents, search_loaded_knowledge_base, search_web, search_arxiv, search_wikipedia]
tool_map = {t.name: t for t in tools}

def run_agent(user_query: str) -> tuple[str, list[dict]]:
    llm_with_tools = get_waterfall_llm(tools=tools)
    messages = [
        SystemMessage(content=(
            "You are ResearchPilot, an autonomous multi-tool AI research agent. You have 5 tools:\n"
            "1. `list_active_vault_documents`: Use this FIRST to see what documents the user has uploaded.\n"
            "2. `search_loaded_knowledge_base`: Search inside the user's uploaded documents.\n"
            "3. `search_web`: Searches live DuckDuckGo web results.\n"
            "4. `search_arxiv`: Searches ArXiv for academic papers.\n"
            "5. `search_wikipedia`: Searches Wikipedia for historical concepts.\n"
            "Never use irrelevant tool results in your final response."
        )),
        HumanMessage(content=user_query)
    ]
    logs = []
    for _ in range(5):
        ai_msg = llm_with_tools.invoke(messages)
        messages.append(ai_msg)
        if not ai_msg.tool_calls:
            break
        for tc in ai_msg.tool_calls:
            t_name, t_args = tc["name"], tc["args"]
            selected = tool_map.get(t_name)
            output = selected.invoke(t_args) if selected else f"Tool {t_name} not found."
            logs.append({
                "tool": t_name,
                "args": t_args,
                "output": str(output)[:600] + "..." if len(str(output)) > 600 else str(output)
            })
            messages.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))

    final_content = messages[-1].content
    final_text = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in final_content) if isinstance(final_content, list) else str(final_content)
    return final_text, logs

if "agent_history" not in st.session_state:
    st.session_state.agent_history = []

for msg in st.session_state.agent_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tool_logs"):
            with st.expander("🛠️ View Agent Tool Calls"):
                for log in msg["tool_logs"]:
                    st.markdown(f"**Tool:** `{log['tool']}` | **Args:** `{log['args']}`")
                    st.caption(log["output"])
                    st.divider()

agent_q = st.chat_input("Ask anything across your vault, ArXiv, Wikipedia, or the web...")
if agent_q:
    st.session_state.agent_history.append({"role": "user", "content": agent_q})
    with st.chat_message("user"):
        st.markdown(agent_q)

    with st.chat_message("assistant"):
        with st.spinner("Agent is reasoning and calling tools..."):
            answer, logs = run_agent(agent_q)
            st.markdown(answer)
            if logs:
                with st.expander("🛠️ View Agent Tool Calls"):
                    for log in logs:
                        st.markdown(f"**Tool:** `{log['tool']}` | **Args:** `{log['args']}`")
                        st.caption(log["output"])
                        st.divider()
            st.session_state.agent_history.append({"role": "assistant", "content": answer, "tool_logs": logs})