import streamlit as st
import time
import random

def apply_custom_theme():
    st.markdown("""
        <style>
            /* Deep Mountain Night Gradient Background */
            .stApp {
                background: linear-gradient(180deg, #0A0F1A 0%, #111827 50%, #1F2937 100%);
                color: #E5E7EB;
            }
            
            /* Glassmorphism for Cards (st.container with border) */
            [data-testid="stVerticalBlockBorderWrapper"] {
                background: rgba(17, 24, 39, 0.4) !important;
                backdrop-filter: blur(12px) !important;
                border: 1px solid rgba(255, 255, 255, 0.08) !important;
                border-radius: 12px !important;
                transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            }
            
            /* Hover Lift Effect for Cards */
            [data-testid="stVerticalBlockBorderWrapper"]:hover {
                transform: translateY(-4px);
                box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
                border-color: rgba(56, 189, 248, 0.4) !important;
            }
            
            /* Hide file dropzone after upload (Targeting the specific container might be tricky globally, but we'll use the trick provided earlier in the specific file) */
            
            /* Custom Pill Badges */
            .badge-doc { background-color: rgba(59, 130, 246, 0.2); color: #60A5FA; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(59, 130, 246, 0.3); }
            .badge-web { background-color: rgba(16, 185, 129, 0.2); color: #34D399; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); }
            .badge-yt  { background-color: rgba(239, 68, 68, 0.2); color: #F87171; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(239, 68, 68, 0.3); }
        </style>
    """, unsafe_allow_html=True)

def render_ai_pulse(status_container):
    """Simulates a live AI news/facts pulse while waiting."""
    facts = [
        "Did you know? Gemini 1.5 Pro can process a 1-million token context window, equal to about 10 novels.",
        "Live AI Pulse: Llama 3 is pushing the boundaries of open-weight logic and reasoning.",
        "Tech Insight: Retrieval-Augmented Generation (RAG) reduces AI hallucinations by grounding answers in your specific facts.",
        "Live AI Pulse: Vector databases like Supabase convert text into high-dimensional numerical space to find semantic meaning.",
        "Did you know? Flash attention mechanisms have dramatically sped up inference times for modern LLMs."
    ]
    pulse_placeholder = status_container.empty()
    for _ in range(15): # Loop for a bit while main thread does work
        pulse_placeholder.markdown(f"**📡 AI Pulse:** *{random.choice(facts)}*")
        time.sleep(2.5)