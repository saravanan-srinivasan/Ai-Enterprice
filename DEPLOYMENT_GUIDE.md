# 🚀 Production Deployment Guide

## Quick Start (5 minutes)

```bash
# 1. Get Groq API key (free, 1 minute)
# - Visit https://console.groq.com/api-keys
# - Sign up if needed
# - Copy your API key

# 2. Set it locally
export GROQ_API_KEY="your-api-key"

# 3. Run deployment check
bash deploy.sh

# 4. Follow the printed instructions
```

---

## Part 1: Deploy Backend to Render (Free Tier Available)

### A. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up (GitHub recommended)
3. Go to dashboard

### B. Deploy Backend Service

1. **New → Web Service**
2. **Connect Repository**
   - Select your GitHub repo
   - Grant permissions
3. **Configure Service**
   - Name: `enterprise-ai-backend` (or custom)
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn api_gateway.main:app --host 0.0.0.0 --port $PORT`
   - Plan: **Starter** ($5/month)
   - Region: Choose closest to users

4. **Add Environment Variables**
   
   Click "Advanced" → "Add Environment Variable":
   
   | Key | Value | Notes |
   |-----|-------|-------|
   | `GROQ_API_KEY` | `sk-...` | From https://console.groq.com/api-keys |
   | `CORS_ORIGINS` | `https://yourdomain.netlify.app,http://localhost:5173` | Your Netlify URL + local dev |
   | `DATA_DIR` | `/opt/render/project/data` | Render persistent storage |
   | `ENVIRONMENT` | `production` | Optional: for logging |

5. **PostgreSQL Service** (Render provides free tier)
   - Render will auto-create `DATABASE_URL` environment variable
   - Already available after service is deployed

6. **Redis Service** (Render provides free tier)
   - Render will auto-create `REDIS_URL` environment variable
   - Already available after service is deployed

7. **Click "Create Web Service"**
   - Wait 3-5 minutes for build + deployment
   - Watch build logs for errors
   - Success: "Your service is live at: https://xxx.onrender.com"

### C. Get Your Backend URL

From Render dashboard:
- Copy the URL: `https://your-service-name.onrender.com`
- Save it for Netlify setup

---

## Part 2: Deploy Frontend to Netlify (Free Tier Available)

### A. Create Netlify Account

1. Go to [netlify.com](https://netlify.com)
2. Sign up (GitHub recommended)
3. Go to dashboard

### B. Deploy Frontend

1. **Add New Site → Import an existing project**
2. **Connect Repository**
   - Select GitHub
   - Select your repo
   - Grant permissions

3. **Configure Deploy Settings**
   - Base directory: `frontend`
   - Build command: `npm install && npm run build`
   - Publish directory: `frontend/dist`

4. **Add Environment Variables**
   
   Click "Site settings" → "Environment":
   
   | Key | Value |
   |-----|-------|
   | `VITE_API_URL` | `https://your-service-name.onrender.com` |

5. **Deploy**
   - Click "Deploy site"
   - Wait 1-2 minutes
   - Success message with your URL: `https://xxxxx.netlify.app`

---

## Part 3: Verify Everything Works

### A. Test Health Endpoint

```bash
curl https://your-service-name.onrender.com/health
# Expected response: {"status":"ok"}
```

### B. Test Frontend

1. Visit `https://xxxxx.netlify.app`
2. You should see the chat interface
3. Try uploading a PDF:
   - Use a sample from `data/sample/`
   - Example: Copy the content of `finance_report_q1_2024.json`
   - Paste into the upload area

4. Ask a question:
   - Example: "What is the total quarterly revenue?"
   - Wait for response from Groq LLM
   - Verify answer appears

### C. Check Backend Logs

On Render dashboard:
- Select your service
- Click "Logs"
- Look for any errors starting with "ERROR"

---

## Common Issues & Fixes

### Issue: "GROQ_API_KEY not found"

**Solution:**
1. Go to Render dashboard
2. Select web service
3. Click "Environment"
4. Add `GROQ_API_KEY` with your actual key
5. Click "Redeploy service"

### Issue: Frontend shows "Cannot connect to API"

**Solution:**
1. Check `VITE_API_URL` environment variable on Netlify
2. Ensure it matches exactly: `https://your-service-name.onrender.com`
3. No trailing slash
4. Redeploy on Netlify

### Issue: "CORS error in browser console"

**Solution:**
1. Go to Render dashboard → Environment Variables
2. Update `CORS_ORIGINS` to include your Netlify domain:
   ```
   https://xxxxx.netlify.app,http://localhost:5173
   ```
3. Click "Redeploy service"

### Issue: "Database connection failed"

**Solution:**
1. Render auto-creates PostgreSQL
2. Wait 5 minutes after service deployment
3. Check logs for `DATABASE_URL` initialization
4. If still failing, restart service on Render

### Issue: Build fails on Render

**Check these:**

1. **Python version**: Confirmed 3.11+
2. **Requirements installed**: Run `pip install -r requirements.txt` locally
3. **Dependencies conflict**: Check `requirements.txt` for duplicates
4. **Missing environment variables**: Render needs `GROQ_API_KEY` before build

---

## Production Best Practices

### A. Monitor Your Services

**Render:**
- Check logs daily for errors
- Monitor CPU/memory usage
- Set up alerts for errors

**Netlify:**
- Check deploy logs
- Monitor 4xx/5xx errors
- Enable Netlify analytics

### B. Cost Optimization

| Service | Tier | Cost | Notes |
|---------|------|------|-------|
| Render Backend | Starter | $5/month | Auto-scales, 100 GB data transfer |
| Render PostgreSQL | Starter | $7/month | Managed, free tier available |
| Render Redis | Starter | $5/month | Managed, free tier available |
| Netlify Frontend | Free | $0/month | Up to 300 deploys/month |
| **Total** | | ~$17/month | Or less with free tiers |

### C. Update CORS Origins

After getting your Netlify URL, always update Render:

```
CORS_ORIGINS=https://xxxxx.netlify.app,http://localhost:5173
```

---

## Troubleshooting Checklist

- [ ] Groq API key obtained from https://console.groq.com/api-keys
- [ ] Groq API key added to Render environment variables
- [ ] Backend deployed to Render with no build errors
- [ ] `DATABASE_URL` created automatically by Render
- [ ] `REDIS_URL` created automatically by Render
- [ ] Backend health check returns `{"status":"ok"}`
- [ ] Frontend `VITE_API_URL` points to correct Render backend
- [ ] Frontend built successfully on Netlify
- [ ] CORS_ORIGINS includes your Netlify domain
- [ ] Test upload + query works end-to-end

---

## Rollback Instructions

### If Render Deploy Fails:

1. Go to Render dashboard
2. Select web service
3. Click "Deployments"
4. Click "Redeploy" next to previous successful version

### If Netlify Deploy Fails:

1. Go to Netlify dashboard
2. Click site
3. Click "Deploys"
4. Click "Publish" on previous successful deploy

---

## Support

- **Render Docs**: https://render.com/docs
- **Netlify Docs**: https://docs.netlify.com
- **Groq API**: https://console.groq.com/docs/text-chat
- **FastAPI Docs**: https://fastapi.tiangolo.com

---

**That's it!** Your production setup should be live in ~15 minutes. 🎉
