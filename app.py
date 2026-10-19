import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from faster_whisper import WhisperModel
from groq import Groq
import uuid
import hashlib
import datetime
import tempfile
import os

st.set_page_config(page_title="Ira — Voice Memory Chatbot", page_icon="🎙️", layout="centered")

st.markdown("""
<div style="text-align:center; padding: 10px 0 5px;">
    <h1>🎙️ Ira</h1>
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
    # IRA_MEMORY_DIR keeps memories on disk across restarts; without it they live in memory
    memory_dir = os.environ.get("IRA_MEMORY_DIR")
    client = chromadb.PersistentClient(path=memory_dir) if memory_dir else chromadb.Client()
    # Chroma's default embedder is all-MiniLM-L6-v2 run with ONNX, so torch is not needed
    emb_fn = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection("chat_memory", embedding_function=emb_fn)
    return collection

def get_groq_key():
    # Environment variable locally and on Render, st.secrets on Streamlit Community Cloud
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            key = ""
    return key

@st.cache_resource
def load_groq():
    key = get_groq_key()
    if not key:
        st.error("GROQ_API_KEY is not set. Export it before launching, or add it to the app's secrets when deployed.")
        st.stop()
    return Groq(api_key=key)

whisper_model  = load_whisper()
memory_collection = load_chroma()
groq_client    = load_groq()

# ── SESSION STATE ──

# The vector store is shared by everyone using the deployed app, so each browser gets
# its own user id, kept in the URL (?user=...). Bookmarking that URL keeps the memories.
if "user_id" not in st.session_state:
    st.session_state.user_id = st.query_params.get("user") or uuid.uuid4().hex[:12]
st.query_params["user"] = st.session_state.user_id

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── MEMORY ──

def save_to_memory(user_msg, bot_msg):
    memory_collection.add(
        documents=[f"User said: {user_msg}\nBot replied: {bot_msg}"],
        ids=[str(uuid.uuid4())],
        metadatas=[{"user_id": st.session_state.user_id,
                    "session_id": st.session_state.session_id,
                    "timestamp": str(datetime.datetime.now())}]
    )

def memory_count():
    return len(memory_collection.get(where={"user_id": st.session_state.user_id}, include=[])["ids"])

def retrieve_memory(query):
    total = memory_count()
    if total == 0:
        return ""
    results = memory_collection.query(query_texts=[query], n_results=min(3, total),
                                      where={"user_id": st.session_state.user_id})
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

# st.audio_input keeps the last recording across reruns, so a clip would be
# handled again on every later interaction. Typed text is checked first, and a
# recording is only transcribed the first time its contents are seen.
if text_input:
    user_message = text_input

elif audio_file is not None:
    audio_bytes = audio_file.getvalue()
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    if audio_hash != st.session_state.get("last_audio_hash"):
        st.session_state.last_audio_hash = audio_hash
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            with st.spinner("Transcribing..."):
                user_message = transcribe(tmp_path)
        except Exception:
            st.error("Couldn't transcribe that recording. Please try again.")
        finally:
            os.unlink(tmp_path)
        if user_message:
            st.toast(f"Heard: {user_message}")

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.write(user_message)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            memory_context = retrieve_memory(user_message)
            try:
                bot_response = get_response(user_message, memory_context)
            except Exception:
                bot_response = None
        if bot_response is None:
            # Groq unavailable or rate-limited: drop the message so the chat history stays consistent
            st.session_state.messages.pop()
            st.error("Ira couldn't reply just now (the language model service is unavailable). Please try again.")
        else:
            save_to_memory(user_message, bot_response)
            st.write(bot_response)

    if bot_response is not None:
        st.session_state.messages.append({"role": "assistant", "content": bot_response})

# ── SIDEBAR ──

with st.sidebar:
    st.markdown("### 🧠 Memory Status")
    st.info(f"Messages remembered: {memory_count()}")
    st.markdown(f"Session ID: `{st.session_state.session_id[:8]}...`")
    if st.button("🔄 New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.markdown("**Stack:** Whisper + ChromaDB + Groq LLaMA 3.1")
    st.markdown("**Built by:** Sparsh Kuwar")
