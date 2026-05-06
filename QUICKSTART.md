# ═══════════════════════════════════════════════════════════════════════════════
# QUICK START GUIDE
# ═══════════════════════════════════════════════════════════════════════════════
# Get the Enterprise AI Assistant running locally in 5 minutes
# ═══════════════════════════════════════════════════════════════════════════════

## ⚡ 5-Minute Local Setup

### 1. Clone & Setup (2 min)

```bash
# Clone repository
git clone <your-repo>
cd enterprise-ai-assistant

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (1 min)

```bash
# Copy example env file
cp .env.example .env

# Edit .env and set:
#   GROQ_API_KEY=<your-api-key-from-console.groq.com>
#   CORS_ORIGINS=http://localhost:3000,http://localhost:5173

nano .env  # or use your editor
```

### 3. Start Backend (1 min)

```bash
# Terminal 1: Backend
uvicorn api_gateway.main:app --reload --host 0.0.0.0 --port 8000

# You should see:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

### 4. Start Frontend (1 min)

```bash
# Terminal 2: Frontend
cd frontend
npm install  # First time only
npm run dev

# You should see:
# ➜  Local:   http://localhost:5173/
```

### 5. Test It! (Open browser)

```
1. Open: http://localhost:5173
2. You should see the chat interface
3. Try uploading a PDF
4. Try asking a question
5. Check DevTools → Network to see API calls
```

---

## 📋 Prerequisites

```bash
# Check you have these installed:
python --version       # Should be 3.10+
node --version         # Should be 18+
npm --version          # Should be 9+

# If not installed:
# - Python: https://python.org
# - Node: https://nodejs.org
```

---

## 🔑 Getting Groq API Key

```
1. Visit: https://console.groq.com/api-keys
2. Sign up (free, takes 1 minute)
3. Copy your API key
4. Paste into .env file: GROQ_API_KEY=<your-key>
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: groq` | Run: `pip install -r requirements.txt` |
| `GROQ_API_KEY not found` | Add to .env and restart backend |
| `Port 8000 in use` | Change to: `--port 8001` |
| `npm command not found` | Install Node.js from nodejs.org |
| `CORS error in browser` | Check CORS_ORIGINS in .env |
| `API returns 500` | Check backend logs for error message |
| `Frontend shows 404` | Ensure backend is running on http://localhost:8000 |

---

## 🧪 Quick Test Commands

```bash
# Test backend health
curl http://localhost:8000/health

# Test backend readiness
curl http://localhost:8000/health/ready

# Test Groq connection
python -c "
from groq import Groq
import os
client = Groq(api_key=os.getenv('GROQ_API_KEY'))
response = client.chat.completions.create(
    model='llama-3.3-70b-versatile',
    messages=[{'role': 'user', 'content': 'Say hello!'}]
)
print(response.choices[0].message.content)
"

# Check frontend build
cd frontend && npm run build
```

---

## 📚 File Structure

```
project/
├── .env                    # Your local config (create from .env.example)
├── requirements.txt        # Python dependencies
├── api_gateway/main.py     # Backend entry point
├── frontend/
│   ├── package.json        # NPM dependencies
│   ├── vite.config.ts      # Vite config
│   └── src/                # React components
├── rag_pipeline/           # RAG logic (Groq, embeddings, vector store)
├── utils/                  # Shared utilities (config, logging, database)
└── data/                   # Data directory (created automatically)
```

---

## 🎯 Common Tasks

### Upload Document from CLI

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/document.pdf"
```

### Submit Query from CLI

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the main topic?",
    "session_id": "test-123",
    "agent_type": "query",
    "top_k": 5,
    "include_sources": true
  }'
```

### View API Documentation

```
http://localhost:8000/docs     # Swagger UI
http://localhost:8000/redoc    # ReDoc
```

### Check Vector Store Stats

```bash
curl http://localhost:8000/health/ready | python -m json.tool
```

---

## 🚀 Deploy to Production

When ready to deploy:

1. **Read** [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions
2. **Get Render account** at www.render.com
3. **Get Netlify account** at www.netlify.com
4. **Push to Git** with configured URLs
5. **Both services auto-deploy** 🎉

---

## 📞 Need Help?

- **Backend Issues**: Check terminal logs
- **Frontend Issues**: Check browser DevTools Console
- **API Issues**: Check `http://localhost:8000/docs`
- **Groq Issues**: Check `https://console.groq.com/docs`

---

## 🎓 Learning Resources

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Vite Docs](https://vitejs.dev)
- [Groq API Docs](https://console.groq.com/docs)
- [Sentence Transformers](https://www.sbert.net)
- [ChromaDB Docs](https://docs.trychroma.com)

---

**Ready to go!** 🚀

Start with: `npm run dev` (frontend) + `uvicorn api_gateway.main:app --reload` (backend)
