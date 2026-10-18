# Ira: interview guide

This guide is for explaining and defending the project in an interview. Each section names the part of `app.py` it describes.

## 1. The 30-second pitch

> Ira is a voice chatbot for Hindi and English speakers that remembers what you told it earlier. Speech is transcribed locally with Whisper. Every exchange is embedded and stored in a ChromaDB vector store, and before each reply the three most relevant past exchanges are retrieved and given to LLaMA 3.1 on Groq. It is retrieval-augmented generation where the "documents" are your own past conversations.

## 2. The 2-minute walkthrough

1. **Input.** The user records audio (`st.audio_input`) or types (`st.chat_input`).
2. **Transcription** (`transcribe`). Audio is written to a temporary `.wav` file and passed to `faster-whisper` (`base` model, CPU, `int8`). Whisper detects the language itself, so there is no Hindi/English toggle.
3. **Memory retrieval** (`retrieve_memory`). The message is embedded with `all-MiniLM-L6-v2` and ChromaDB returns the 3 nearest stored exchanges.
4. **Prompt building** (`get_response`). System prompt (persona and "reply in the user's language") + retrieved memories + the last 10 chat messages + the new message.
5. **Generation.** Groq `llama-3.1-8b-instant`, `max_tokens=300`, `temperature=0.8`.
6. **Memory write** (`save_to_memory`). The pair `"User said: … Bot replied: …"` is stored with a session id and timestamp.

## 3. Two kinds of memory (the main design idea)

| | Short-term | Long-term |
|---|---|---|
| What | Last 10 messages of this session | Every exchange ever stored |
| How | Sent as chat history | Semantic search, top 3 |
| Good at | Keeping the current thread coherent | Recalling something from much earlier |
| Cost | Grows with the window, so it is capped at 10 | Fixed: always 3 snippets |

**Why not send the whole history?** Tokens cost money and latency, and an 8B model has a limited context. Retrieval sends only what is relevant to the current message.

**Why store the user message and the reply together?** A memory is more useful with its context. "User said: my exam is on Friday / Bot replied: good luck" retrieves better than either half alone.

## 4. Why each technology

| Choice | Why | Alternative I considered |
|---|---|---|
| `faster-whisper` | Runs Whisper locally, about 4x faster than the reference implementation, `int8` on CPU. Audio never leaves the machine. Handles Hindi. | OpenAI Whisper API: simpler, but costs money and sends audio to a third party |
| `base` Whisper model | Good speed/accuracy balance on a laptop CPU | `small`/`medium`: better Hindi accuracy, noticeably slower |
| ChromaDB | Embedded vector DB, no server to run, built-in embedding functions | FAISS (lower level, no metadata), Pinecone (hosted, overkill) |
| `all-MiniLM-L6-v2` | Small (about 80 MB), fast, 384-dim vectors | A multilingual model, which would be better for Hindi (see weaknesses) |
| Groq + LLaMA 3.1 8B | Very low latency, important for a voice app. Free tier. | GPT-4o-mini: stronger, but slower and paid |
| `temperature=0.8` | Conversational, less robotic replies | Lower values for factual assistants |
| Streamlit | A chat UI with a mic widget in about 100 lines of Python | React + FastAPI: more control, much more code |
| `@st.cache_resource` | Streamlit reruns the whole script on every interaction. Caching loads models once per process instead of every message. | |

## 5. Weaknesses to state openly

Say these before the interviewer finds them. Knowing your project's limits reads as maturity.

1. **Memory is in-process only.** `chromadb.Client()` is an in-memory client, so memories are lost when the app restarts. *Fix:* `chromadb.PersistentClient(path="memory_db")`, a one-line change.
2. **Memory is not filtered by session or user.** The session id is stored as metadata but `query()` has no `where` filter. Fine for one user. For several users I would add `where={"user_id": ...}`.
3. **The embedding model is English-centric.** `all-MiniLM-L6-v2` was trained mostly on English, so Hindi (especially Devanagari) memories retrieve less reliably. *Fix:* `paraphrase-multilingual-MiniLM-L12-v2` or `intfloat/multilingual-e5-small`.
4. **(Fixed) Recorded audio used to be reprocessed on reruns.** Streamlit keeps the last recording in `st.audio_input` across reruns, and the old code checked audio before text, so after one recording every typed message was ignored and the same clip was transcribed and answered again. Now typed text is checked first, and a clip is only transcribed when the SHA-256 hash of its bytes differs from `st.session_state.last_audio_hash`. This is a good story for "tell me about a bug you fixed": the cause was a framework behaviour (Streamlit reruns the whole script and widgets keep their values), not a logic slip.
5. **The current conversation is stored and retrieved twice.** Recent exchanges are in both the 10-message window and the vector store, so retrieval can return what is already in the window. *Fix:* exclude the current session's latest N exchanges from retrieval.
6. **No relevance threshold.** Top 3 are always added, even when nothing is related. *Fix:* drop results above a distance cutoff.
7. **No `requirements.txt`, tests or error handling** around the Groq call. If Groq is down, the app shows a stack trace.

## 6. Likely interview questions

**Q: How is this different from a normal chatbot?**
A normal chatbot only sees its context window. Ira also searches every earlier exchange by meaning and brings back the relevant ones, so it can recall something from much earlier without sending the whole history.

**Q: What is an embedding?**
A list of numbers (here 384) that represents the meaning of a text. Texts with similar meaning get vectors that are close together, so "I have an exam Friday" and "my test is this week" are neighbours even though they share few words.

**Q: How does ChromaDB find similar memories?**
It embeds the query with the same model and returns the stored vectors with the smallest distance. By default it uses an HNSW index, an approximate nearest-neighbour graph, so search stays fast as the store grows.

**Q: Why Groq?**
Latency. In a voice app, a 3-second wait feels broken. Groq runs LLaMA on custom hardware (LPUs) with very high tokens per second.

**Q: How does it handle Hindi?**
Whisper detects the spoken language itself. The system prompt tells the model to reply in the user's language. The weak point is retrieval, because the embedding model is English-centric (weakness 3).

**Q: What happens with Hinglish (code-mixed speech)?**
Whisper usually transcribes it in one script, often Latin for Hinglish. The LLM handles mixed text well. Testing with real Hinglish samples is something I would add.

**Q: How would you make this production-ready?**
Persistent and per-user memory, a multilingual embedding model, a relevance cutoff, error handling and retries around Groq, a `requirements.txt` with pinned versions, and tests for `retrieve_memory` and prompt building. For scale, run Whisper as its own service, possibly on a GPU.

**Q: Privacy concerns?**
Transcription is local, but message text and retrieved memories go to Groq. Memories are personal data, so production would need consent, deletion ("forget this") and encryption at rest.

**Q: Why `max_tokens=300`?**
Short replies suit conversation and voice, and keep latency and cost down.

## 7. How this relates to service AI (if asked why it is on a Bruviti resume)

The same pattern, retrieve relevant history and give it to the LLM, is how a service assistant would recall a customer's or a machine's past tickets before answering. Voice input matters for technicians whose hands are busy on site.

## 8. What I would build next

1. Persistent, per-user memory with a "forget" command.
2. A multilingual embedding model plus a relevance threshold.
3. Automated tests (Streamlit's `AppTest` can drive the chat and audio widgets with the models stubbed out).
4. Text-to-speech replies, for a full voice loop.
5. Memory summarisation: compress old exchanges into facts ("user's exam is Friday") instead of raw transcripts.
