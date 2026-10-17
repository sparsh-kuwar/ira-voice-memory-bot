# Ira: Hindi-English Voice Memory Chatbot

A voice chatbot that understands Hindi and English and recalls earlier parts of the conversation by meaning, not just the last few messages.

## What it does

- **Voice or text input.** Speak into the browser microphone or type. Speech is transcribed locally with Whisper (`faster-whisper`, `base` model, CPU, int8), which detects Hindi or English automatically.
- **Long-term memory through semantic search.** Each exchange is embedded with `all-MiniLM-L6-v2` and stored in ChromaDB. Before every reply, the 3 most similar past exchanges are retrieved and added to the system prompt.
- **Short-term memory.** The last 10 messages of the current session are sent with every request.
- **Replies in the user's language.** LLaMA 3.1 8B (`llama-3.1-8b-instant`) through the Groq API, with a warm, concise persona.
- **Streamlit UI** with a chat view, a microphone widget and a sidebar showing how many exchanges are stored.

## How a message flows

```text
Microphone ──► Whisper (local) ──┐
                                 ├──► user message
Text box ────────────────────────┘          │
                                            ▼
                         ChromaDB: top-3 similar past exchanges
                                            │
                                            ▼
             system prompt + memories + last 10 messages ──► Groq LLaMA 3.1
                                            │
                                            ▼
                         reply shown, exchange saved to ChromaDB
```

## Stack

`streamlit` · `faster-whisper` · `chromadb` · `sentence-transformers` · `groq` · `soundfile` · `numpy`

## Run locally

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install streamlit faster-whisper chromadb sentence-transformers groq soundfile numpy
export GROQ_API_KEY="your_key_here"
streamlit run app.py
```

The first run downloads the Whisper and embedding models, so it takes a minute.

## Current limitations

- **Memory lasts only while the app runs.** The app uses `chromadb.Client()`, which keeps data in memory. Restarting Streamlit clears it. Switching to `chromadb.PersistentClient(path="memory_db")` would keep it on disk.
- **Memory is shared across sessions.** Each memory is tagged with a session id, but retrieval does not filter by it, so "New Session" still sees older memories. That is intended for one user. Several users would need a per-user filter.
- **Single user, no accounts.**

See [EXPLANATION.md](EXPLANATION.md) for a full walkthrough of the design and the trade-offs.

## Built by

Sparsh Kuwar, B.Tech Computer Engineering, JSPM's Rajarshi Shahu College of Engineering
