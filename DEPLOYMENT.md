# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT GUIDE — Enterprise AI Assistant (Render + Netlify)
# ═══════════════════════════════════════════════════════════════════════════════

## 📋 Overview

This guide covers deployment of the Enterprise AI Assistant:
- **Backend**: FastAPI + Python → **Render**
- **Frontend**: React + TypeScript + Vite → **Netlify**
- **LLM**: Groq API (llama-3.3-70b-versatile)
- **Embeddings**: Sentence-Transformers (local, no OpenAI)
- **Database**: PostgreSQL (Render)
- **Cache**: Redis (Render)

---

## ✅ Pre-Deployment Checklist

### Backend
- [ ] `GROQ_API_KEY` obtained from https://console.groq.com/api-keys
- [ ] `requirements.txt` updated (no OpenAI, has Groq)
- [ ] All `localhost` references removed
- [ ] Config uses environment variables
- [ ] `.env.example` is correct

### Frontend
- [ ] No hardcoded API URLs (uses VITE_API_URL)
- [ ] `npm run build` succeeds without errors
- [ ] `netlify.toml` configured correctly
- [ ] Frontend `.env.example` created

### Infrastructure
- [ ] `render.yaml` configured
- [ ] Render account created (www.render.com)
- [ ] Netlify account created (www.netlify.com)
- [ ] Git repository connected to both services

---

## 🚀 STEP 1: Backend Deployment (Render)

### 1.1 Create Render Database (PostgreSQL)

```bash
# Via Render dashboard:
1. Sign up: https://dashboard.render.com
2. New → PostgreSQL
3. Name: enterprise-ai-db
4. Plan: Standard (or free if available)
5. Copy DATABASE_URL
```

### 1.2 Create Render Redis Cache

```bash
# Via Render dashboard:
1. New → Redis
2. Name: enterprise-ai-redis
3. Plan: Standard (or free if available)
4. Copy REDIS_URL
```

### 1.3 Deploy Backend Service

```bash
# Via Render dashboard:
1. New → Web Service
2. Connect Git repository
3. Name: enterprise-ai-backend
4. Environment: Python
5. Build Command: pip install -r requirements.txt
6. Start Command: uvicorn api_gateway.main:app --host 0.0.0.0 --port $PORT
7. Plan: Starter (low-cost) or Standard

# Environment Variables (set in Render dashboard):
DATABASE_URL=<from PostgreSQL service>
REDIS_URL=<from Redis service>
GROQ_API_KEY=<your-groq-api-key>
SECRET_KEY=<generate-random-32-char-string>
APP_ENV=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.netlify.app
DATA_DIR=/opt/render/project/data

# Disk for persistent storage:
1. Add Disk → Mount at /opt/render/project/data
2. Size: 10GB (adjust as needed)
```

### 1.4 Verify Backend Deployment

```bash
curl https://<your-backend>.onrender.com/health
# Should return: {"status": "alive", "service": "Enterprise AI Knowledge Assistant", ...}

curl https://<your-backend>.onrender.com/health/ready
# Should return: {"status": "healthy", "checks": {...}}
```

---

## 🎨 STEP 2: Frontend Deployment (Netlify)

### 2.1 Update netlify.toml

Replace placeholders in `netlify.toml`:

```toml
[build.environment]
  VITE_API_URL = "https://your-backend-render-url.onrender.com"

[context.production.environment]
  VITE_API_URL = "https://your-backend-render-url.onrender.com"
```

### 2.2 Deploy Frontend

```bash
# Via Netlify dashboard:
1. Sign up: https://app.netlify.com
2. New site → Import an existing project
3. Connect Git repository
4. Configure:
   - Base directory: frontend
   - Build command: npm install && npm run build
   - Publish directory: frontend/dist
5. Deploy

# Or via CLI:
npm install -g netlify-cli
cd frontend
netlify deploy
```

### 2.3 Configure Environment Variables

```bash
# Via Netlify dashboard:
1. Site settings → Build & deploy → Environment
2. Add environment variables:
   VITE_API_URL=https://<your-backend>.onrender.com

# Or in netlify.toml (see above)
```

### 2.4 Verify Frontend Deployment

```bash
1. Visit: https://your-site.netlify.app
2. Check browser console for errors
3. Try uploading a document
4. Try submitting a query
```

---

## 🔧 STEP 3: Configure CORS

### Backend (Render)
Ensure `render.yaml` or environment has:
```
CORS_ORIGINS=https://yourdomain.netlify.app
```

### Test CORS
```bash
curl -H "Origin: https://yourdomain.netlify.app" \
     -H "Access-Control-Request-Method: POST" \
     https://<your-backend>.onrender.com/api/v1/query
```

---

## 🧪 STEP 4: Testing

### 4.1 Backend Tests

```bash
# Test health endpoint
curl https://<your-backend>.onrender.com/health

# Test ready probe
curl https://<your-backend>.onrender.com/health/ready

# Test query endpoint
curl -X POST https://<your-backend>.onrender.com/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is test query?",
    "session_id": "test-session",
    "agent_type": "query",
    "top_k": 5,
    "include_sources": true
  }'

# Test document upload
curl -X POST https://<your-backend>.onrender.com/api/v1/upload \
  -F "file=@sample.pdf"
```

### 4.2 Frontend Tests

```bash
1. Navigate to https://yourdomain.netlify.app
2. Upload test document
3. Submit test query
4. Check DevTools Network tab for API calls
5. Verify CORS headers are present
```

### 4.3 Groq API Test

```bash
# In Python:
from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Say hello"}]
)
print(response.choices[0].message.content)
```

---

## 📊 MONITORING & TROUBLESHOOTING

### Backend Logs (Render)

```bash
1. Render dashboard → your backend service
2. Logs tab → view real-time logs
3. Check for errors, especially during startup
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `GROQ_API_KEY not found` | Add to Render environment variables |
| `DATABASE_URL invalid` | Copy from Render PostgreSQL service |
| `REDIS_URL invalid` | Copy from Render Redis service |
| `CORS error` | Update CORS_ORIGINS in Render environment |
| `Port bind error` | Ensure PORT env var is read correctly |
| `Vector DB not found` | Check /opt/render/project/data disk is mounted |
| `Frontend 404` | Ensure netlify.toml has SPA redirects |
| `API calls fail` | Check VITE_API_URL matches backend URL |

---

## 🔐 Security Checklist

- [ ] `SECRET_KEY` is unique and >16 characters
- [ ] `GROQ_API_KEY` never committed to git
- [ ] `DATABASE_URL` and `REDIS_URL` never committed
- [ ] `.env.production.local` in `.gitignore`
- [ ] `DEBUG=false` in production
- [ ] HTTPS enforced (automatic on Render & Netlify)
- [ ] CORS origins restricted to your domain
- [ ] Rate limiting enabled (60 req/min default)
- [ ] Regular backups configured for PostgreSQL
- [ ] Log retention configured

---

## 💰 COST OPTIMIZATION

### Render (Backend)

- **Starter Plan**: $5/month (for web service)
- **PostgreSQL**: Free tier available (0.5GB)
- **Redis**: Free tier available (0.5GB)
- **Disk**: $0.25/GB/month for persistent storage
- **Estimate**: $5-15/month for low traffic

### Netlify (Frontend)

- **Starter Plan**: FREE for static sites
- **Bandwidth**: 100GB/month included
- **Functions**: 125K invocations/month free
- **Estimate**: FREE for low traffic

### Groq API

- **Free tier**: Available (generous limits)
- **Pay-as-you-go**: $0.10 per 1M tokens
- **Estimate**: FREE for demo use (within limits)

**Total monthly cost**: ~$10-20 for production-ready hosting!

---

## 📈 SCALING

### Horizontal Scaling (Render)

```yaml
# In render.yaml:
autoscaling:
  enabled: true
  minInstances: 1
  maxInstances: 3
```

### Vertical Scaling

- Increase Render plan (Standard, Pro)
- Upgrade PostgreSQL plan
- Upgrade Redis plan
- Increase disk size

---

## 🔄 CONTINUOUS DEPLOYMENT

### Auto-Deploy on Push

Both Render and Netlify automatically deploy when you push to your Git repository.

```bash
# Workflow:
1. Make code changes
2. git commit -m "Update backend"
3. git push origin main
4. Render automatically rebuilds and deploys
5. Frontend automatically rebuilds on Netlify
```

---

## 📚 USEFUL COMMANDS

### Local Development

```bash
# Backend
cd project_root
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
export GROQ_API_KEY=your-key
export DATABASE_URL=postgresql://...
uvicorn api_gateway.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
# Visit http://localhost:5173
```

### Local Testing with Real Backend

```bash
# Update frontend/.env.local:
VITE_API_URL=https://<your-backend>.onrender.com

# Then restart frontend dev server
npm run dev
```

---

## 🆘 SUPPORT

- **Groq API Issues**: https://console.groq.com/docs
- **Render Docs**: https://render.com/docs
- **Netlify Docs**: https://docs.netlify.com
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Vite Docs**: https://vitejs.dev

---

## ✨ NEXT STEPS

1. Set up monitoring/alerting
2. Configure automatic backups
3. Set up custom domain
4. Add analytics (Netlify/PostHog)
5. Set up error tracking (Sentry)
6. Configure rate limiting alerts
7. Document API endpoints
8. Create user guides

---

**Last Updated**: May 6, 2026
**Version**: 1.0.0 (Production-Ready)
