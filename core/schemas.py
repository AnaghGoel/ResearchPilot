from pydantic import BaseModel, Field
from typing import Optional

class KnowledgeReport(BaseModel):
    title: str = Field(description="Clear, descriptive title of the document, article, or video")
    executive_overview: str = Field(description="High-level introduction and context of the material")
    core_theme_or_problem: str = Field(description="The central thesis, problem statement, or main subject addressed")
    key_takeaways: list[str] = Field(description="5 to 7 most important actionable or conceptual takeaways")
    deep_dive_analysis: str = Field(description="Detailed breakdown of methodology, arguments, architecture, or core chapters")
    practical_insights: str = Field(description="Key findings, real-world applications, results, or examples")
    important_concepts: list[str] = Field(description="Key technical terms, mental models, or definitions introduced")
    strengths: Optional[list[str]] = Field(default=None, description="Strengths or novel contributions if identifiable")
    limitations: Optional[list[str]] = Field(default=None, description="Limitations, caveats, or open questions if identifiable")
    conclusion: str = Field(description="Final synthesis and concluding summary")

class Flashcard(BaseModel):
    front: str = Field(description="Concept name or concise question on the front of the card")
    back: str = Field(description="Clear, accurate explanation or answer on the back of the card")

class FlashcardDeck(BaseModel):
    cards: list[Flashcard]

class MCQQuestion(BaseModel):
    question: str = Field(description="A clear multiple-choice question testing understanding of the material")
    options: list[str] = Field(description="Exactly 4 options labeled clearly")
    correct_option_index: int = Field(description="Index (0, 1, 2, or 3) of the correct option in the options list")
    explanation: str = Field(description="Brief explanation of why the correct answer is right based on the source")

class QuizData(BaseModel):
    questions: list[MCQQuestion]

class Slide(BaseModel):
    slide_title: str = Field(description="A clear, concise title for the slide")
    bullet_points: list[str] = Field(description="3 to 5 concise bullet points summarizing the core concepts, definitions, or comparisons")
    speaker_notes: str = Field(description="Detailed explanation of the slide content for the presenter to read")

class Presentation(BaseModel):
    slides: list[Slide] = Field(description="A sequential list of slides covering the entire document from start to finish")