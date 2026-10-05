import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from typing import Optional
from pydantic import BaseModel, Field

load_dotenv()

llm=ChatGoogleGenerativeAI(model="gemini-3.6-flash",temperature=1)
import os

print(os.getenv("GOOGLE_API_KEY"))

class ResearchReport(BaseModel):
    title: str=Field(description="The title of the research report")
    introduction: str=Field(description="Give a breif description about the research report")
    problem: str=Field(description="The problem statement of the research report")
    key_idea: str=Field(description="The key idea of the research report")
    methodology: str=Field(description="The methodology used in the research report")
    findings: str=Field(description="The findings of the research report")
    conclusion: str=Field(description="The conclusion of the research report")
    important_concepts: list[str]=Field(default=None,description="Highlight the important 5 concepts of the research report in bullet points")
    strengths: Optional[list[str]] = None
    limitations: Optional[list[str]] = None


st.set_page_config(
    page_title="ResearchPilot",
    page_icon="📚",
    layout="wide"
)

structured_llm=llm.with_structured_output(ResearchReport)

prompt=PromptTemplate(template=
    """
    You are an expert research assistant.

    Analyze the following research material and create a structured
    research report.

    Research material:
    {research_text}

    Follow these requirements:

    1. Give a suitable title.
    2. Explain the introduction.
    3. Clearly identify the problem being addressed.
    4. Explain the key idea.
    5. Explain the methodology.
    6. Summarize the findings.
    7. Give a concise conclusion.
    8. Extract the most important concepts.
    9. Mention strengths when they can be identified.
    10. Mention limitations when they can be identified.

    Do not invent information that is not present in the research material.

    Research material:
    {research_text}
    """,
    input_variables=["research_text"]
)

st.title("📚ResearchPilot")

st.write("AI powered research assistant that helps you analyze research material and generate structured research reports.")

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

if analyze:

    if not research_text.strip():
        st.warning("Please enter some research material.")
    else:

        final_prompt = prompt.invoke({
    "research_text": research_text
})

        with st.spinner("Analyzing research..."):

            result = structured_llm.invoke(final_prompt)

        st.success("Research analysis completed!")

        st.divider()

        st.header(result.title)

        st.subheader("Introduction")
        st.write(result.introduction)

        st.subheader("Problem")
        st.write(result.problem)

        st.subheader("Key Idea")
        st.write(result.key_idea)

        st.subheader("Methodology")
        st.write(result.methodology)

        st.subheader("Findings")
        st.write(result.findings)

        st.subheader("Important Concepts")

        for concept in result.important_concepts:
            st.markdown(f"- {concept}")

        if result.strengths:
            st.subheader("Strengths")

            for strength in result.strengths:
                st.markdown(f"- {strength}")

        if result.limitations:
            st.subheader("Limitations")

            for limitation in result.limitations:
                st.markdown(f"- {limitation}")

        st.subheader("Conclusion")
        st.write(result.conclusion)