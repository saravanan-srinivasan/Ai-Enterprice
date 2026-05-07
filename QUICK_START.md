# 🚀 QUICK START - 5 Minutes to Production

Your Enterprise AI Assistant is **production-ready** and waiting to deploy! Here's exactly what to do next.

---

## Step 1: Get Your Groq API Key (1 minute)

```
1. Visit: https://console.groq.com/api-keys
2. Sign up (free, 1 minute)
3. Create API key
4. Copy it (starts with "sk-")
5. Save it safely
```

✅ **Done!** You now have the ONLY external API key needed.

---

## Step 2: Test Locally (3 minutes)

```bash
# Set your Groq API key
export GROQ_API_KEY="sk-your-actual-key"

# Run checks
bash deploy.sh

# Expected output: ✅ ALL CHECKS PASSED - READY TO DEPLOY
```

**If anything fails**, check [CHECKLIST.md](CHECKLIST.md#-troubleshooting) for fixes.

---

## Step 3: Deploy to Production (1 minute setup, ~10 min deploy)

### Backend to Render (5 minutes)

1. Go to [render.com](https://render.com)
2. Create account (GitHub recommended)
3. New → Web Service → Connect your GitHub repo
4. Configure:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn api_gateway.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variable: `GROQ_API_KEY=sk-...`
6. Deploy
7. Copy your backend URL (e.g., `https://xxx.onrender.com`)

### Frontend to Netlify (5 minutes)

1. Go to [netlify.com](https://netlify.com)
2. Create account (GitHub recommended)
3. New → Import from Git → Select your repo
4. Configure:
   - Base directory: `frontend`
   - Build: `npm install && npm run build`
   - Publish: `frontend/dist`
5. Set environment variable: `VITE_API_URL=https://your-render-backend.onrender.com`
6. Deploy
7. You get a URL like `https://xxx.netlify.app`

---

## Step 4: Final CORS Fix (1 minute)

After you have your Netlify URL:

1. Go to Render dashboard
2. Select your web service
3. Environment → Edit `CORS_ORIGINS`
4. Change to: `https://your-netlify-domain.netlify.app,http://localhost:5173`
5. Save & Redeploy

---

## Step 5: Test Production (2 minutes)

```bash
# Test health
curl https://your-render-backend.onrender.com/health
# Expected: {"status":"ok"}
```

Open your Netlify URL in browser:
1. ✅ Chat interface loads
2. ✅ Click "Upload" → upload a PDF
3. ✅ Ask a question → Groq responds
4. ✅ No red errors in browser console (F12)

---

## ✨ You're Live!

Your AI assistant is now on the internet. Share your Netlify URL with anyone!

---

## 📚 Need Help?

| Issue | Solution |
|-------|----------|
| "Can't deploy" | See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) (step-by-step) |
| "Verification failed" | See [CHECKLIST.md](CHECKLIST.md#-troubleshooting) |
| "API won't respond" | Check Render logs: dashboard → service → Logs |
| "Frontend won't load" | Check browser console (F12) for red errors |
| "CORS error" | Ensure `CORS_ORIGINS` includes your Netlify domain |

---

## 💰 Cost Breakdown

| Service | Tier | Cost |
|---------|------|------|
| Render Backend | Starter | $5/month |
| Render PostgreSQL | Starter | $7/month |
| Render Redis | Starter | $5/month |
| Netlify Frontend | Free | $0/month |
| **Total** | | **~$17/month** |

Or use free tiers for even cheaper prototypes.

---

## 🎓 Full Documentation

| Document | Purpose | Time |
|----------|---------|------|
| [README.md](README.md) | Project overview & features | 10 min |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Complete deployment instructions | 15 min |
| [CHECKLIST.md](CHECKLIST.md) | Pre-deployment validation | 10 min |
| [.env.example](.env.example) | All environment variables | Reference |

---

**Ready?** Start with Step 1 above, or if you hit issues, jump to [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed help.

Good luck! 🚀
