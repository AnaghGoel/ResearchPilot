import os
import streamlit as st
import datetime
import re
import io
from collections import Counter
from pptx import Presentation as PPTXPresentation
from dotenv import load_dotenv

from supabase.client import Client, create_client
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnableSequence, RunnablePassthrough, RunnableLambda

from core.engine import get_waterfall_llm
from core.schemas import KnowledgeReport, FlashcardDeck, QuizData, Presentation
from core.loaders import format_docs

load_dotenv()
import random

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# -----------------------------
# Dynamic Retrieval & UX Helpers
# -----------------------------
def compute_dynamic_k(total_chunks: int, query: str = "", mode: str = "qa") -> int:
    if total_chunks <= 0: return 1
    if mode == "overview":
        if total_chunks <= 8: return total_chunks
        elif total_chunks <= 40: return min(12, max(6, int(total_chunks * 0.35)))
        else: return 15
    if mode == "study_tools":
        return min(total_chunks, max(8, min(24, int(total_chunks * 0.40))))

    broad_keywords = {"summarize", "summary", "overall", "compare", "comparison", "difference", "all", "list", "main", "key", "themes", "chapters", "methodology", "findings"}
    is_broad_query = bool(set(query.lower().split()).intersection(broad_keywords)) or len(query.split()) > 18
    if is_broad_query:
        return min(total_chunks, min(max(6, int(total_chunks * 0.20)), 10))
    return min(total_chunks, 4)

def get_smart_retriever(vector_store, total_chunks: int, query: str = "", mode: str = "qa", report_id: str = None):
    k = compute_dynamic_k(total_chunks, query=query, mode=mode)
    search_kwargs = {"k": k}
    
    if report_id:
        search_kwargs["filter"] = {"report_id": report_id}

    # CRITICAL FIX: Changed search_type to "similarity" exclusively. 
    # This prevents the (45,0) matrix mismatch error caused by LangChain's MMR implementation with Supabase.
    return vector_store.as_retriever(search_type="similarity", search_kwargs=search_kwargs), k

def calculate_adaptive_item_count(total_chunks: int, item_type: str = "quiz") -> int:
    if total_chunks <= 12:
        return 5
    elif item_type == "ppt":
        return min(20, max(5, int(total_chunks * 0.35)))
    else:
        return min(25, max(5, int(total_chunks * 0.35)))

def get_full_document_context(vector_store, total_chunks: int, report_id: str) -> str:
    study_retriever, k = get_smart_retriever(
        vector_store,
        total_chunks=total_chunks,
        query="core concepts chapters definitions theories comparisons findings methods conclusion",
        mode="study_tools",
        report_id=report_id
    )
    docs = study_retriever.invoke("concepts definitions methodology results summary")
    return format_docs(docs)

def generate_xray(text: str) -> tuple[int, int, list[str]]:
    clean_text = re.sub(r'[^a-zA-Z\s]', '', text.lower())
    words = clean_text.split()
    word_count = len(words)
    read_time = max(1, word_count // 200)
    stop_words = {"the", "and", "a", "of", "to", "in", "is", "that", "it", "for", "on", "with", "as", "this", "by", "from", "are", "be", "an", "was"}
    keywords = [w for w in words if w not in stop_words and len(w) > 4]
    top_words = [word[0] for word in Counter(keywords).most_common(5)]
    return word_count, read_time, top_words

def build_pptx_file(presentation_data: Presentation) -> bytes:
    prs = PPTXPresentation()
    for slide_data in presentation_data.slides:
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        
        slide.shapes.title.text = slide_data.slide_title
        body_shape = slide.placeholders[1]
        tf = body_shape.text_frame
        tf.text = slide_data.bullet_points[0] if slide_data.bullet_points else ""
        for point in slide_data.bullet_points[1:]:
            p = tf.add_paragraph()
            p.text = point
            p.level = 0
            
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = slide_data.speaker_notes

    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    pptx_stream.seek(0)
    return pptx_stream.getvalue()

# -----------------------------
# Prompts
# -----------------------------
analysis_prompt = PromptTemplate(template="""You are an expert knowledge synthesizer. Analyze the following material and generate a comprehensive structured report.\nExplanation style: {style}\nDetail level: {length}\nMaterial:\n{research_text}""", input_variables=["research_text", "style", "length"])
summary_prompt = PromptTemplate(template="""Summarize the following material clearly.\nExplanation style: {style}\nDetail level: {length}\nMaterial:\n{research_text}""", input_variables=["research_text", "style", "length"])
questions_prompt = PromptTemplate(template="""Based on the following material, generate 5 important open-ended study questions.\nExplanation style: {style}\nMaterial:\n{research_text}""", input_variables=["research_text", "style"])
rag_prompt = PromptTemplate(template="""You are a precise knowledge assistant. Answer using ONLY the provided context.\nPrevious Conversation:\n{chat_history}\nRetrieved Context:\n{context}\nUser Question:\n{question}\nAnswer:""", input_variables=["chat_history", "context", "question"])
flashcard_prompt = PromptTemplate(template="""Create exactly {count} high-yield study flashcards (front and back) covering all major topics across the material.\nDo not cluster all cards around one topic—distribute them evenly.\nStyle: {style}\nMaterial:\n{research_text}""", input_variables=["count", "style", "research_text"])
quiz_prompt = PromptTemplate(template="""Create a comprehensive {count}-question multiple-choice quiz (4 options each) testing deep comprehension across different sections of the material.\nEnsure correct_option_index is an integer (0, 1, 2, or 3).\nStyle: {style}\nMaterial:\n{research_text}""", input_variables=["count", "style", "research_text"])
ppt_prompt = PromptTemplate(template="""Act as an instructional designer. Distill the sequential flow of the entire document into a comprehensive {count}-slide presentation.\nStructure:\n1. Title & Agenda\n2. Foundational Concepts & Definitions\n3. In-depth Section/Chapter Analyses\n4. Comparative Perspectives & Methodologies\n5. Conclusions & Key Takeaways\n\nEnsure each slide has 3-5 substantive bullet points and detailed speaker notes.\nStyle: {style}\nMaterial:\n{research_text}""", input_variables=["count", "style", "research_text"])

# -----------------------------
# Core Execution & Rendering
# -----------------------------
def run_initial_analysis(report_id: str, vector_store, chunk_count: int, style: str, length: str, source_label: str = "Document", source_name: str = "File", namespace: str = "doc") -> str:
    with st.status("🚀 Launching ResearchPilot Engine...", expanded=True) as status:
        st.write(f"✅ Extracted **{chunk_count}** semantic chunks from source.")
        
        overview_retriever, used_k = get_smart_retriever(vector_store, total_chunks=chunk_count, mode="overview", report_id=report_id)
        core_docs = overview_retriever.invoke("main overview introduction core problem key arguments methodology findings takeaways conclusion")
        overview_text = format_docs(core_docs)
        
        wc, rt, top_words = generate_xray(overview_text)
        st.info(f"**Instant Source X-Ray:** 📝 ~{wc} words | ⏱️ {rt} min human read time | 🏷️ Top themes: {', '.join(top_words)}")
        
        st.write(f"🔄 Running Dynamic Retrieval (selected {used_k} optimal cross-sections)...")
        st.write("🧠 Synthesizing structured report, executive summary, and study questions...")

        llm = get_waterfall_llm()
        structured_llm = get_waterfall_llm(structured_schema=KnowledgeReport)

        chain = RunnableParallel({
            "report": RunnableSequence(analysis_prompt, structured_llm),
            "summary": RunnableSequence(summary_prompt, llm, StrOutputParser()),
            "questions": RunnableSequence(questions_prompt, llm, StrOutputParser())
        })

        try:
            result = chain.invoke({"research_text": overview_text, "style": style, "length": length})
            result["overview_text"] = overview_text
            result["chunk_count"] = chunk_count
            result["overview_k"] = used_k
            status.update(label="✅ Knowledge Synthesis Complete!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="❌ Synthesis Failed", state="error", expanded=True)
            st.error(f"LLM API Error: {str(e)}")
            st.stop()

    report_dict = result["report"].dict() if hasattr(result["report"], "dict") else result["report"]
    
    payload = {
        "report_id": report_id,
        "title": report_dict.get("title", "Untitled Report"),
        "source_type": source_label,
        "source_name": source_name,
        "namespace": namespace,
        "result_json": {
            "summary": result["summary"],
            "questions": result["questions"],
            "report": report_dict,
            "overview_text": result["overview_text"],
            "chunk_count": result["chunk_count"],
            "overview_k": result["overview_k"]
        }
    }

    try:
        supabase.table("saved_reports").insert(payload).execute()
    except Exception as e:
        st.error(f"Failed to save report to cloud database: {e}")

    if "saved_reports" not in st.session_state: 
        st.session_state["saved_reports"] = {}
        
    st.session_state["saved_reports"][report_id] = {
        "report_id": report_id,
        "title": payload["title"],
        "type": source_label,
        "source_name": source_name,
        "namespace": namespace,
        "route": f"views/{'document' if namespace=='doc' else 'article' if namespace=='web' else 'youtube'}_studio.py",
        "time": datetime.datetime.now().strftime("%b %d, %I:%M %p"),
        "vector_store": vector_store,
        "result": payload["result_json"],
        "chat": [],
        "quiz": None,
        "flashcards": None,
        "pptx_binary": None
    }

    st.session_state[f"{namespace}_active_report"] = report_id
    return report_id

def render_knowledge_workspace(namespace: str):
    report_id = st.session_state.get(f"{namespace}_active_report")
    if not report_id or "saved_reports" not in st.session_state or report_id not in st.session_state["saved_reports"]:
        return

    data = st.session_state["saved_reports"][report_id]
    result = data["result"]
    vector_store = data["vector_store"]
    total_chunks = result.get("chunk_count", 10)
    style = st.session_state.get("style", "Academic")

    default_quiz_count = calculate_adaptive_item_count(total_chunks, "quiz")
    default_ppt_count = calculate_adaptive_item_count(total_chunks, "ppt")

    st.divider()
    left_col, right_col = st.columns([6, 4], gap="large")

    with left_col:
        tab1, tab2, tab3 = st.tabs(["📊 Structured Report", "📌 Summary & Questions", "🎯 Active Recall & PPT"])

        with tab1:
            report_data = result["report"]
            st.subheader(report_data.get("title", ""))
            st.caption(f"Source: `{data['source_name']}` | Synthesized from **{result.get('overview_k', total_chunks)}** sections of **{total_chunks}** total chunks.")
            st.markdown("#### Executive Overview\n" + report_data.get("executive_overview", ""))
            st.markdown("#### Core Theme / Problem\n" + report_data.get("core_theme_or_problem", ""))
            st.markdown("#### Key Takeaways")
            for item in report_data.get("key_takeaways", []): st.markdown(f"- {item}")
            st.markdown("#### Deep-Dive Analysis\n" + report_data.get("deep_dive_analysis", ""))
            st.markdown("#### Practical Insights & Findings\n" + report_data.get("practical_insights", ""))
            st.markdown("#### Key Concepts & Terminology")
            for concept in report_data.get("important_concepts", []): st.markdown(f"- {concept}")
            if report_data.get("strengths"):
                st.markdown("#### Strengths")
                for s in report_data["strengths"]: st.markdown(f"- {s}")
            if report_data.get("limitations"):
                st.markdown("#### Limitations / Caveats")
                for l in report_data["limitations"]: st.markdown(f"- {l}")
            st.markdown("#### Conclusion\n" + report_data.get("conclusion", ""))

        with tab2:
            st.subheader("📌 Executive Summary")
            st.write(result["summary"])
            st.divider()
            st.subheader("🎯 Open-Ended Review Questions")
            st.markdown(result["questions"])

        with tab3:
            st.subheader("🎯 Adaptive Study Tools & Presentations")
            st.caption(f"Document size: **{total_chunks}** chunks. Target: **{default_quiz_count}** questions/cards and **{default_ppt_count}** slides.")
            
            with st.expander("⚙️ Customize Generation Target", expanded=False):
                col_s1, col_s2 = st.columns(2)
                with col_s1: custom_study_count = st.slider("MCQ / Flashcard Count", 5, 25, default_quiz_count, key=f"study_{report_id}")
                with col_s2: custom_ppt_count = st.slider("Presentation Slides Count", 5, 20, default_ppt_count, key=f"ppt_{report_id}")

            col_a, col_b, col_c = st.columns(3)
            with col_a: gen_fc = st.button(f"🃏 Flashcards ({custom_study_count})", use_container_width=True, key=f"fc_{report_id}")
            with col_b: gen_quiz = st.button(f"📝 MCQ Quiz ({custom_study_count})", use_container_width=True, key=f"quiz_btn_{report_id}")
            with col_c: gen_ppt = st.button(f"📽️ PPTX Slides ({custom_ppt_count})", type="primary", use_container_width=True, key=f"ppt_btn_{report_id}")

            if gen_fc:
                with st.spinner(f"Sampling entire document and generating {custom_study_count} flashcards..."):
                    study_context = get_full_document_context(vector_store, total_chunks, report_id)
                    fc_llm = get_waterfall_llm(structured_schema=FlashcardDeck)
                    deck = (flashcard_prompt | fc_llm).invoke({"count": custom_study_count, "style": style, "research_text": study_context})
                    data["flashcards"] = deck.cards

            if gen_quiz:
                with st.spinner(f"Synthesizing {custom_study_count} multiple-choice questions across all chapters..."):
                    study_context = get_full_document_context(vector_store, total_chunks, report_id)
                    quiz_llm = get_waterfall_llm(structured_schema=QuizData)
                    q_data = (quiz_prompt | quiz_llm).invoke({"count": custom_study_count, "style": style, "research_text": study_context})
                    data["quiz"] = q_data.questions

            if gen_ppt:
                with st.spinner(f"Designing sequential {custom_ppt_count}-slide presentation..."):
                    study_context = get_full_document_context(vector_store, total_chunks, report_id)
                    ppt_llm = get_waterfall_llm(structured_schema=Presentation)
                    presentation_data = (ppt_prompt | ppt_llm).invoke({"count": custom_ppt_count, "style": style, "research_text": study_context})
                    data["pptx_binary"] = build_pptx_file(presentation_data)

            if data.get("pptx_binary"):
                st.success("✅ Presentation compiled successfully!")
                st.download_button("📥 Download Presentation (.pptx)", data=data["pptx_binary"], file_name=f"{report_id}_presentation.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)
                st.divider()

            if data.get("flashcards"):
                st.markdown(f"### 🃏 Study Flashcards ({len(data['flashcards'])} Cards)")
                for idx, card in enumerate(data["flashcards"], 1):
                    with st.expander(f"📌 Card {idx}: {card.front}"): st.success(f"**Explanation:** {card.back}")

            if data.get("quiz"):
                st.divider()
                st.markdown(f"### 📝 Self-Test Quiz ({len(data['quiz'])} Questions)")
                questions = data["quiz"]
                with st.form(key=f"quiz_form_{report_id}"):
                    user_answers = {}
                    for i, q in enumerate(questions):
                        st.markdown(f"**Q{i+1}. {q.question}**")
                        user_answers[i] = st.radio("Select:", options=q.options, index=None, key=f"q_{report_id}_{i}", label_visibility="collapsed")
                        st.write("")
                    if st.form_submit_button("✅ Grade Quiz"):
                        score = 0
                        for i, q in enumerate(questions):
                            correct_opt = q.options[q.correct_option_index]
                            if user_answers.get(i) == correct_opt:
                                score += 1
                                st.success(f"**Q{i+1}: Correct!** ({correct_opt})\n\n*{q.explanation}*")
                            else:
                                st.error(f"**Q{i+1}: Incorrect.** You chose: `{user_answers.get(i)}` | Correct: `{correct_opt}`\n\n*{q.explanation}*")
                        st.metric("Final Quiz Score", f"{score} / {len(questions)}")

    with right_col:
        st.subheader("💬 Chat with Source")
        st.caption("Ask specific questions grounded in this document.")
        chat_container = st.container(height=550)
        with chat_container:
            for msg in data["chat"]:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])

        user_q = st.chat_input("Ask a question...", key=f"rag_input_{report_id}")
        if user_q:
            data["chat"].append({"role": "user", "content": user_q})
            with chat_container:
                with st.chat_message("user"): st.markdown(user_q)
                retriever, dynamic_k = get_smart_retriever(vector_store, total_chunks=total_chunks, query=user_q, mode="qa", report_id=report_id)
                history_str = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in data["chat"][-6:-1])

                rag_chain = (
                    RunnableParallel({"context": retriever | RunnableLambda(format_docs), "question": RunnablePassthrough(), "chat_history": lambda _: history_str})
                    | rag_prompt | get_waterfall_llm() | StrOutputParser()
                )

                with st.chat_message("assistant"):
                    with st.spinner("Retrieving context..."):
                        answer = rag_chain.invoke(user_q)
                        st.markdown(answer)
                        with st.expander(f"🔍 Source Chunks (k={dynamic_k})"):
                            for idx, doc in enumerate(retriever.invoke(user_q), 1):
                                st.markdown(f"**Chunk {idx} (Page {doc.metadata.get('page', 'N/A')}):**")
                                st.caption(doc.page_content)
                                st.divider()
                data["chat"].append({"role": "assistant", "content": answer})

def get_random_ai_fact():
    facts = [
        "Gemini 1.5 Pro can process a 1-million token context window, equal to about 10 novels at once.",
        "Retrieval-Augmented Generation (RAG) dramatically reduces AI hallucinations by grounding answers in your specific facts.",
        "Vector databases like Supabase convert text into high-dimensional numerical space to find semantic meaning mathematically.",
        "Flash attention mechanisms have dramatically sped up inference times for modern LLMs this year."
    ]
    return random.choice(facts)

def run_initial_analysis(report_id: str, vector_store, chunk_count: int, style: str, length: str, source_label: str = "Document", source_name: str = "File", namespace: str = "doc") -> str:
    with st.status("🚀 Launching ResearchPilot Engine...", expanded=True) as status:
        st.write(f":material/check_circle: Extracted **{chunk_count}** semantic chunks from source.")
        
        overview_retriever, used_k = get_smart_retriever(vector_store, total_chunks=chunk_count, mode="overview", report_id=report_id)
        core_docs = overview_retriever.invoke("main overview introduction core problem key arguments methodology findings takeaways conclusion")
        overview_text = format_docs(core_docs)
        
        wc, rt, top_words = generate_xray(overview_text)
        st.info(f"**Instant Source X-Ray:** :material/edit_document: ~{wc} words | :material/timer: {rt} min human read time | :material/label: Top themes: {', '.join(top_words)}")
        
        st.markdown(f"**📡 AI Pulse:** *{get_random_ai_fact()}*")
        
        st.write(f":material/sync: Running Dynamic Retrieval (selected {used_k} optimal cross-sections)...")
        st.write(":material/psychology: Synthesizing structured report, executive summary, and study questions...")

        llm = get_waterfall_llm()
        structured_llm = get_waterfall_llm(structured_schema=KnowledgeReport)

        chain = RunnableParallel({
            "report": RunnableSequence(analysis_prompt, structured_llm),
            "summary": RunnableSequence(summary_prompt, llm, StrOutputParser()),
            "questions": RunnableSequence(questions_prompt, llm, StrOutputParser())
        })

        try:
            result = chain.invoke({"research_text": overview_text, "style": style, "length": length})
            result["overview_text"] = overview_text
            result["chunk_count"] = chunk_count
            result["overview_k"] = used_k
            status.update(label="✅ Knowledge Synthesis Complete!", state="complete", expanded=False)
            st.toast("Synthesis Complete!", icon=":material/task_alt:")
        except Exception as e:
            status.update(label="❌ Synthesis Failed", state="error", expanded=True)
            st.error(f"LLM API Error: {str(e)}")
            st.stop()

    # --- THE FIX: Bulletproof parsing for Pydantic V1, V2, or standard dictionaries ---
    report_obj = result.get("report", {})
    if isinstance(report_obj, dict):
        report_dict = report_obj
    elif hasattr(report_obj, "model_dump"):
        report_dict = report_obj.model_dump() # Pydantic V2
    elif hasattr(report_obj, "dict"):
        report_dict = report_obj.dict() # Pydantic V1
    else:
        report_dict = {}

    payload = {
        "report_id": report_id,
        "title": report_dict.get("title", "Untitled Report"),
        "source_type": source_label,
        "source_name": source_name,
        "namespace": namespace,
        "result_json": {
            "summary": result["summary"],
            "questions": result["questions"],
            "report": report_dict,
            "overview_text": result["overview_text"],
            "chunk_count": result["chunk_count"],
            "overview_k": result["overview_k"]
        }
    }

    try:
        supabase.table("saved_reports").insert(payload).execute()
    except Exception as e:
        st.error(f"Failed to save report to cloud database: {e}")

    if "saved_reports" not in st.session_state: 
        st.session_state["saved_reports"] = {}
        
    st.session_state["saved_reports"][report_id] = {
        "report_id": report_id,
        "title": payload["title"],
        "type": source_label,
        "source_name": source_name,
        "namespace": namespace,
        "route": f"views/{'document' if namespace=='doc' else 'article' if namespace=='web' else 'youtube'}_studio.py",
        "time": datetime.datetime.now().strftime("%b %d, %I:%M %p"),
        "vector_store": vector_store,
        "result": payload["result_json"],
        "chat": [],
        "quiz": None,
        "flashcards": None,
        "pptx_binary": None
    }

    st.session_state[f"{namespace}_active_report"] = report_id
    return report_id