# 🔧 Pre-Deployment Checklist

This checklist ensures your Enterprise AI Assistant is ready to deploy to **Render + Netlify** with **Groq API only**.

## ✅ Quick Fixes (5 minutes)

### Before You Deploy

- [ ] **Groq API Key**
  - [ ] Get key from https://console.groq.com/api-keys (FREE signup required)
  - [ ] Key starts with `sk-` (verify in console)
  - [ ] Save securely (used in next step)

- [ ] **Backend Environment Variables**
  - [ ] Copy `.env.production` to `.env` locally
  - [ ] Update `GROQ_API_KEY` with your actual key
  - [ ] Update `CORS_ORIGINS` with your Netlify domain (when you know it)
  - [ ] Leave `DATABASE_URL` and `REDIS_URL` empty (Render provides them)

- [ ] **Frontend Environment Variables**
  - [ ] Open [netlify.toml](netlify.toml)
  - [ ] Update `VITE_API_URL` placeholder with your Render backend URL (after deployment)
  - [ ] No hardcoded localhost references

---

## 🧪 Local Testing (10 minutes)

### Test Backend Startup

```bash
# Terminal 1: Start backend
export GROQ_API_KEY="your-actual-api-key"
python -m pip install -r requirements.txt
uvicorn api_gateway.main:app --reload --host 0.0.0.0 --port 8000

# Should see:
# ✅ Uvicorn running on http://0.0.0.0:8000
# ✅ API docs at http://localhost:8000/docs
```

### Test API Health

```bash
# Terminal 2: Test health endpoint
curl http://localhost:8000/health
# Expected response: {"status":"ok"}
```

### Test Frontend Build

```bash
# Terminal 3: Build frontend
cd frontend
npm install
npm run build

# Expected output:
# ✅ dist/index.html created
# ✅ No build errors
```

### Check for Common Errors

Look for these in terminal output (NONE should appear):

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'openai'` | ✓ Already fixed (OpenAI removed) |
| `ModuleNotFoundError: No module named 'anthropic'` | ✓ Already fixed (Anthropic removed) |
| `GROQ_API_KEY not found` | Set `export GROQ_API_KEY="..."`  |
| `Cannot connect to PostgreSQL` | OK for local (using SQLite backup) |
| `Cannot connect to Redis` | OK for local (using in-memory backup) |
| `SentenceTransformer failed to load` | Run `pip install -r requirements.txt` |

---

## 🚀 Deployment Checklist

### Step 1: Prepare Repository

- [ ] Commit all changes: `git add . && git commit -m "Production deployment ready"`
- [ ] Push to GitHub: `git push origin main`
- [ ] Verify code is on GitHub (go to your repo and check)

### Step 2: Render Backend Deployment

- [ ] Create Render account (render.com)
- [ ] Create Web Service from your GitHub repo
- [ ] Configure:
  - [ ] Build command: `pip install -r requirements.txt`
  - [ ] Start command: `uvicorn api_gateway.main:app --host 0.0.0.0 --port $PORT`
  - [ ] Plan: Starter ($5/month)
- [ ] Set environment variables:
  - [ ] `GROQ_API_KEY` = your actual key
  - [ ] `CORS_ORIGINS` = (update after getting Netlify URL)
  - [ ] `ENVIRONMENT` = production
  - [ ] `DATA_DIR` = /opt/render/project/data

- [ ] Wait for deployment (~5 minutes)
  - [ ] Watch build logs for errors
  - [ ] Success: "Your service is live"
  - [ ] Copy backend URL (e.g., `https://xxx.onrender.com`)

### Step 3: Netlify Frontend Deployment

- [ ] Create Netlify account (netlify.com)
- [ ] Import GitHub repository
- [ ] Configure:
  - [ ] Base directory: `frontend`
  - [ ] Build: `npm install && npm run build`
  - [ ] Publish: `frontend/dist`
  - [ ] Environment variable:
    - [ ] `VITE_API_URL` = `https://xxx.onrender.com` (from Render)

- [ ] Deploy
  - [ ] Watch deploy logs
  - [ ] Success: "Publish complete"
  - [ ] Copy Netlify URL (e.g., `https://xxx.netlify.app`)

### Step 4: Fix CORS After Getting URLs

- [ ] Go to Render dashboard
- [ ] Select web service
- [ ] Edit `CORS_ORIGINS` to include Netlify domain:
  ```
  https://xxxxx.netlify.app,http://localhost:5173
  ```
- [ ] Redeploy service

---

## 🧪 Production Testing

### Test 1: Health Check

```bash
curl https://your-render-url.onrender.com/health
# Expected: {"status":"ok"}
```

### Test 2: Frontend Loading

- [ ] Visit `https://your-domain.netlify.app`
- [ ] Page loads without errors
- [ ] Chat interface visible
- [ ] Browser console (F12) has NO red errors

### Test 3: Upload Document

- [ ] Click "Upload" button
- [ ] Choose a PDF from `data/sample/`
- [ ] Wait for "Upload successful"
- [ ] Check backend logs for processing

### Test 4: Query API

- [ ] Type: "What is in this document?"
- [ ] Click "Send"
- [ ] Wait for Groq response (~3-10 seconds)
- [ ] Answer appears in chat

### Test 5: Check for Errors

Look in browser console (F12 → Console tab) for:
- [ ] No "Cannot connect to API" errors
- [ ] No CORS errors
- [ ] No `undefined` references

---

## 🆘 Troubleshooting

### Backend Build Fails on Render

**Error in logs**: `ModuleNotFoundError` or `pip install failed`

**Fix:**
1. Check `requirements.txt` has no syntax errors
2. Try locally: `pip install -r requirements.txt`
3. Rebuild on Render dashboard

### Frontend Says "Cannot Connect to API"

**Error in browser console**: `Failed to fetch from ...`

**Fixes to try:**
1. Check `VITE_API_URL` is set correctly on Netlify
2. Verify Render backend is running (test health endpoint)
3. Check `CORS_ORIGINS` includes Netlify domain
4. Redeploy both services

### "GROQ_API_KEY not found" Error

**Fix:**
1. Go to Render dashboard
2. Select web service
3. Go to "Environment"
4. Add `GROQ_API_KEY` with your actual key
5. Click "Redeploy service"

### Rate Limiting from Groq

**Error**: "Rate limit exceeded" after many requests

**Expected behavior**: Groq free tier has 30 requests/minute limit
- This is fine for demos
- For production: Upgrade Groq plan or implement caching

---

## 📊 Cost Summary

| Service | Tier | Cost | Auto-Scale |
|---------|------|------|-----------|
| Render Backend | Starter | $5/month | No (1 worker) |
| Render PostgreSQL | Starter | $7/month | No |
| Render Redis | Starter | $5/month | No |
| **Netlify Frontend** | **Free** | **$0/month** | Yes |
| **TOTAL** | | **~$17/month** | Partial |

Or use free tiers for smaller deployments (~$3/month).

---

## ✨ You're Done!

Once all tests pass:
- [ ] Your app is live on the internet
- [ ] Using only Groq API (no OpenAI costs)
- [ ] Fully managed by Render + Netlify
- [ ] Automatic deploys on GitHub push
- [ ] Share the Netlify URL with anyone

**Congrats! 🎉**

For questions:
- Render: https://render.com/docs
- Netlify: https://docs.netlify.com
- Groq: https://console.groq.com/docs
