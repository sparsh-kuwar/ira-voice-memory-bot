# Ira: Hindi-English Voice Memory Chatbot

A voice chatbot that understands Hindi and English and recalls earlier parts of the conversation by meaning, not just the last few messages.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sparsh-kuwar/ira-voice-memory-bot)

One click deploys it on Render's free plan. You only need a free Groq API key (see [Deploy on Render](#deploy-on-render-free-plan)).

## What it does

- **Voice or text input.** Speak into the browser microphone or type. By default speech is transcribed locally with Whisper (`faster-whisper`, `base` model, CPU, int8). On Render it uses Groq's hosted `whisper-large-v3-turbo` instead (see Deploy). Both detect Hindi or English automatically.
- **Long-term memory through semantic search.** Each exchange is embedded with `all-MiniLM-L6-v2` (Chroma's built-in ONNX version, so no PyTorch) and stored in ChromaDB. Before every reply, the 3 most similar past exchanges *of the same user* are retrieved and added to the system prompt.
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

`streamlit` · `faster-whisper` · `chromadb` · `groq` (versions pinned in `requirements.txt`)

## Run locally

```bash
python3.12 -m venv venv          # Python 3.11–3.13
source venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your_key_here"   # free key from console.groq.com
streamlit run app.py
```

Instead of exporting the key, you can copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and put it there. That file is gitignored.

The first run downloads the Whisper and embedding models (about 220 MB), so it takes a minute.

## Deploy on Render (free plan)

The repo includes a Render Blueprint (`render.yaml`). The quickest way is the button:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sparsh-kuwar/ira-voice-memory-bot)

Or do it by hand:

1. In the Render dashboard, choose **New → Blueprint** and select this repository.
2. When asked, enter your `GROQ_API_KEY` (a free key from console.groq.com). It is stored as a secret in Render and is never committed.
3. Click **Apply**. When the build finishes, open the service URL.

**Why Render transcribes with Groq.** Render's free plan has 512 MB of RAM. Measured peak memory:

| Setup | Peak RAM |
|---|---|
| Local Whisper `base` + embedder | ~680 MB (too much) |
| Local Whisper `tiny` + embedder | ~530 MB (too much) |
| Groq hosted Whisper + embedder | **~300 MB** |

So `render.yaml` sets `IRA_TRANSCRIBER=groq`. The same Groq key is used, no local speech model is loaded, and `whisper-large-v3-turbo` is more accurate for Hindi than `base`. The trade-off is that recordings are sent to Groq; with the default `local` setting they never leave the machine.

On the free plan the service sleeps after 15 minutes without traffic. The next visit takes about a minute to wake up, and memories kept in RAM are cleared. The first message after a start also downloads the 80 MB embedding model.

## Deploy (Streamlit Community Cloud, free)

1. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and click **Create app**.
2. Pick this repository, branch `main` and main file `app.py`.
3. Open **Advanced settings**, choose Python 3.12, and paste this into **Secrets**:
   ```toml
   GROQ_API_KEY = "your_groq_key_here"
   ```
4. Click **Deploy**. The first start takes a few minutes while it installs packages and downloads the models.

Here the app can keep local Whisper, because Streamlit Community Cloud allows more than the ~700 MB it needs. Microphone access requires HTTPS, which both deployed URLs provide.

Optional settings (environment variables):

| Variable | Effect |
|---|---|
| `GROQ_API_KEY` | Required. Read from the environment or from `st.secrets`. |
| `IRA_TRANSCRIBER` | `local` (default): faster-whisper on the server. `groq`: Groq's hosted `whisper-large-v3-turbo`, no local model. |
| `WHISPER_MODEL` | Local Whisper size, default `base` (`tiny`, `small` … also work). |
| `IRA_MEMORY_DIR` | Store memories on disk in this folder instead of in memory. Only useful on a host with a persistent disk. |

## Current limitations

- **Memory lasts only while the app runs.** By default memories are kept in memory, so a restart (or the free host putting the app to sleep) clears them. Setting `IRA_MEMORY_DIR` keeps them on disk where the host has a persistent disk.
- **Users are identified by a link, not an account.** Each browser gets a random id in the URL (`?user=…`), and retrieval only searches that user's memories. Bookmarking the URL keeps your memories. Anyone with the link can see them, so it isn't real authentication.
- **The Groq key is shared.** Everyone using the deployed app uses the owner's Groq key and its free-tier rate limit. If the limit is hit, Ira shows a friendly error instead of crashing.

See [EXPLANATION.md](EXPLANATION.md) for a full walkthrough of the design and the trade-offs.

## Built by

Sparsh Kuwar, B.Tech Computer Engineering, JSPM's Rajarshi Shahu College of Engineering
