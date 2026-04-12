cat > README.md << 'EOF'
# Ira — Hindi-English Voice Memory Chatbot

A voice-powered conversational AI that remembers past conversations and understands both Hindi and English.

## What it does
- 🎙️ Voice input via Whisper (auto-detects Hindi/English)
- 🧠 Persistent memory via ChromaDB vector store
- 💬 Emotionally intelligent responses via Groq LLaMA 3.1
- 🌐 Clean UI via Streamlit

## Stack
`faster-whisper` · `chromadb` · `sentence-transformers` · `groq` · `streamlit`

## Run locally
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install streamlit faster-whisper chromadb sentence-transformers groq soundfile numpy
export GROQ_API_KEY="your_key_here"
streamlit run app.py
```

## Built by
Sparsh Kuwar — B.Tech Computer Engineering, JSPM's Rajarshi Shahu College of Engineering
EOF

git add README.md
git commit -m "docs: add README"
