import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

def get_waterfall_llm(structured_schema=None, tools=None):
    """
    Creates a highly available LLM chain using Google's latest models 
    which offer massive token limits and 1M context windows on the free tier.
    """
    
    # 1. Frontline: Gemini 3.8 Flash (State-of-the-art intelligence & massive context)
    llm_1 = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.2, max_retries=1)
    
    # 2. Fallback: Gemini 3.5 Flash-Lite (High throughput execution)
    llm_2 = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0.2, max_retries=1)

    if tools:
        llm_1 = llm_1.bind_tools(tools)
        llm_2 = llm_2.bind_tools(tools)
        
    # Apply structured output binding if a schema is passed
    elif structured_schema:
        llm_1 = llm_1.with_structured_output(structured_schema)
        llm_2 = llm_2.with_structured_output(structured_schema)

    # Create the silent fallback waterfall
    waterfall_chain = llm_1.with_fallbacks([llm_2])

    return waterfall_chain

def get_embeddings():
    """Returns the local embedding model for vector generation."""
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")