import streamlit as st

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel,RunnableSequence
from langchain_google_genai import ChatGoogleGenerativeAI

from pydantic import BaseModel
from typing import Optional


# -----------------------------
# Configuration
# -----------------------------

load_dotenv()

st.set_page_config(
    page_title="ResearchPilot",
    page_icon="📚",
    layout="wide"
)


# -----------------------------
# Structured Output Model
# -----------------------------

class ResearchReport(BaseModel):
    title: str
    introduction: str
    problem: str
    key_idea: str
    methodology: str
    findings: str
    conclusion: str
    important_concepts: list[str]
    strengths: Optional[list[str]] = None
    limitations: Optional[list[str]] = None


# -----------------------------
# LLM
# -----------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.7,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)
structured_llm = llm.with_structured_output(ResearchReport)


# -----------------------------
# Prompts
# -----------------------------

analysis_prompt = PromptTemplate(
    template="""
You are an expert research assistant.

Analyze the following research material and create a structured
research report.

Explanation style: {style}
Explanation length: {length}

Research material:
{research_text}

Requirements:

1. Give a suitable title.
2. Explain the introduction.
3. Identify the main problem.
4. Explain the key idea.
5. Explain the methodology.
6. Summarize the findings.
7. Give a conclusion.
8. Extract important concepts.
9. Mention strengths when identifiable.
10. Mention limitations when identifiable.

Do not invent information that is not present in the research material.
""",
    input_variables=["research_text", "style", "length"]
)


summary_prompt = PromptTemplate(
    template="""
Summarize the following research material.

Explanation style: {style}
Explanation length: {length}

Research material:
{research_text}

Give a clear and useful summary.
""",
    input_variables=["research_text", "style", "length"]
)


questions_prompt = PromptTemplate(
    template="""
Based on the following research material, generate 5 important
questions that someone studying this topic should be able to answer.

Research material:
{research_text}

Explanation style: {style}

Give only the questions as a numbered list.
""",
    input_variables=["research_text", "style"]
)

# -----------------------------
# Parallel Chain
# -----------------------------

research_chain = RunnableParallel({
    'report': RunnableSequence(analysis_prompt, structured_llm),
    'summary' : RunnableSequence(summary_prompt,llm,StrOutputParser()),
    'questions': RunnableSequence(questions_prompt, llm, StrOutputParser())
})


# -----------------------------
# Streamlit UI
# -----------------------------

st.title("📚 ResearchPilot")

st.write(
    "AI-powered research analysis and explanation assistant"
)

st.divider()


research_text = st.text_area(
    "Paste your research paper / article / technical content",
    height=300,
    placeholder="Paste your research material here..."
)


col1, col2 = st.columns(2)

with col1:
    style = st.selectbox(
        "Explanation Style",
        [
            "Academic",
            "Beginner Friendly",
            "Interview Preparation",
            "Technical"
        ]
    )

with col2:
    length = st.selectbox(
        "Explanation Length",
        [
            "Short",
            "Medium",
            "Detailed"
        ]
    )


analyze = st.button(
    "🔍 Analyze Research",
    type="primary"
)


# -----------------------------
# Execute
# -----------------------------

if analyze:

    if not research_text.strip():

        st.warning("Please enter some research material.")

    else:

        input_data = {
            "research_text": research_text,
            "style": style,
            "length": length
        }

        with st.spinner("Analyzing research..."):

            result = research_chain.invoke(input_data)

        st.success("Research analysis completed!")

        # -----------------------------
        # Summary
        # -----------------------------

        st.header("📌 Summary")

        st.write(result["summary"])


        # -----------------------------
        # Detailed Report
        # -----------------------------

        st.header("📊 Detailed Report")

        report = result["report"]

        st.subheader(report.title)

        st.subheader("Introduction")
        st.write(report.introduction)

        st.subheader("Problem")
        st.write(report.problem)

        st.subheader("Key Idea")
        st.write(report.key_idea)

        st.subheader("Methodology")
        st.write(report.methodology)

        st.subheader("Findings")
        st.write(report.findings)

        st.subheader("Important Concepts")

        for concept in report.important_concepts:
            st.markdown(f"- {concept}")


        if report.strengths:

            st.subheader("Strengths")

            for strength in report.strengths:
                st.markdown(f"- {strength}")


        if report.limitations:

            st.subheader("Limitations")

            for limitation in report.limitations:
                st.markdown(f"- {limitation}")


        st.subheader("Conclusion")
        st.write(report.conclusion)


        # -----------------------------
        # Study Questions
        # -----------------------------

        st.header("🎯 Study Questions")

        st.markdown(result["questions"])