import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from faster_whisper import WhisperModel
from groq import Groq
import uuid
import datetime
import numpy as np
import soundfile as sf
import tempfile
import os

st.set_page_config(page_title="Ira — Voice Memory Chatbot", page_icon="🎙️", layout="centered")

st.markdown("""
<div style="text-align:center; padding: 10px 0 5px;">
    <h1 style="color:#1a1a4e;">🎙️ Ira</h1>
    <p style="color:#555;">Voice-powered · Remembers you · Hindi & English</p>
    <p style="color:#aaa; font-size:0.8rem;">Built by Sparsh Kuwar · Whisper + ChromaDB + Groq</p>
</div>
""", unsafe_allow_html=True)

# ── LOAD MODELS (cached so they only load once) ──

@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

@st.cache_resource
def load_chroma():
    client = chromadb.Client()
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection("chat_memory", embedding_function=emb_fn)
    return collection

@st.cache_resource
def load_groq():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        st.error("Set GROQ_API_KEY: run `export GROQ_API_KEY='your_key'` in terminal before launching.")
        st.stop()
    return Groq(api_key=key)

whisper_model  = load_whisper()
memory_collection = load_chroma()
groq_client    = load_groq()

# ── SESSION STATE ──

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── MEMORY ──

def save_to_memory(user_msg, bot_msg):
    memory_collection.add(
        documents=[f"User said: {user_msg}\nBot replied: {bot_msg}"],
        ids=[str(uuid.uuid4())],
        metadatas=[{"session_id": st.session_state.session_id,
                    "timestamp": str(datetime.datetime.now())}]
    )

def retrieve_memory(query):
    total = memory_collection.count()
    if total == 0:
        return ""
    results = memory_collection.query(query_texts=[query], n_results=min(3, total))
    if not results["documents"] or not results["documents"][0]:
        return ""
    return "\n\nRelevant past memories:\n" + "\n".join(f"- {m}" for m in results["documents"][0])

# ── TRANSCRIBE ──

def transcribe(audio_path):
    segments, _ = whisper_model.transcribe(audio_path)
    return " ".join(seg.text for seg in segments).strip()

# ── LLM ──

def get_response(user_message, memory_context):
    system = """You are Ira, a warm and emotionally intelligent AI assistant.
You understand both Hindi and English, responding in whichever language the user uses.
You remember past conversations and reference them naturally when relevant.
You are empathetic, curious, and genuinely interested in the person you talk to.
Keep responses concise and human."""

    messages = [{"role": "system", "content": system + memory_context}]
    for m in st.session_state.messages[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        max_tokens=300,
        temperature=0.8
    )
    return resp.choices[0].message.content

# ── CHAT DISPLAY ──

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── INPUT ──

st.divider()
col1, col2 = st.columns([1, 2])

with col1:
    audio_file = st.audio_input("🎙️ Speak (Hindi or English)")

with col2:
    text_input = st.chat_input("Or type here in Hindi or English...")

# ── PROCESS INPUT ──

user_message = None

if audio_file is not None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_file.read())
        tmp_path = f.name
    with st.spinner("Transcribing..."):
        user_message = transcribe(tmp_path)
    os.unlink(tmp_path)
    if user_message:
        st.toast(f"Heard: {user_message}")

elif text_input:
    user_message = text_input

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.write(user_message)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            memory_context = retrieve_memory(user_message)
            bot_response = get_response(user_message, memory_context)
            save_to_memory(user_message, bot_response)
        st.write(bot_response)

    st.session_state.messages.append({"role": "assistant", "content": bot_response})

# ── SIDEBAR ──

with st.sidebar:
    st.markdown("### 🧠 Memory Status")
    st.info(f"Messages remembered: {memory_collection.count()}")
    st.markdown(f"Session ID: `{st.session_state.session_id[:8]}...`")
    if st.button("🔄 New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.markdown("**Stack:** Whisper + ChromaDB + Groq LLaMA 3.1")
    st.markdown("**Built by:** Sparsh Kuwar")
