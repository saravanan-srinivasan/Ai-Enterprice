#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# RENDER + NETLIFY DEPLOYMENT FIX SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

set -e

echo "🚀 Enterprise AI Assistant - Production Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Verify Groq API Key
echo ""
echo "📋 STEP 1: Verify Groq API Key"
echo "───────────────────────────────────────────────────────────────────────────────"
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ ERROR: GROQ_API_KEY not set"
    echo ""
    echo "Get your Groq API key:"
    echo "1. Visit: https://console.groq.com/api-keys"
    echo "2. Sign up (free, 1 minute)"
    echo "3. Copy your API key"
    echo ""
    echo "Then set it:"
    echo "  export GROQ_API_KEY='your-api-key-here'"
    exit 1
else
    echo "✅ GROQ_API_KEY is set"
fi

# Step 2: Verify Python Dependencies
echo ""
echo "📋 STEP 2: Verify Dependencies"
echo "───────────────────────────────────────────────────────────────────────────────"
python -c "import groq; print('✅ groq package OK')" 2>/dev/null || {
    echo "❌ Groq not installed"
    echo "Run: pip install -r requirements.txt"
    exit 1
}
python -c "import fastapi; print('✅ FastAPI OK')" 2>/dev/null || {
    echo "❌ FastAPI not installed"
    echo "Run: pip install -r requirements.txt"
    exit 1
}

# Step 3: Test Backend Start
echo ""
echo "📋 STEP 3: Test Backend Startup"
echo "───────────────────────────────────────────────────────────────────────────────"
echo "Testing backend initialization..."
python -c "
from api_gateway.main import app
print('✅ Backend initialized successfully')
" || {
    echo "❌ Backend initialization failed"
    exit 1
}

# Step 4: Test Frontend Build
echo ""
echo "📋 STEP 4: Test Frontend Build"
echo "───────────────────────────────────────────────────────────────────────────────"
cd frontend
npm run build > /dev/null 2>&1 && {
    echo "✅ Frontend builds successfully"
} || {
    echo "❌ Frontend build failed"
    echo "Run: cd frontend && npm install && npm run build"
    exit 1
}
cd ..

# Step 5: Verify Environment Variables
echo ""
echo "📋 STEP 5: Environment Variables"
echo "───────────────────────────────────────────────────────────────────────────────"
echo "Required for Render:"
echo "  ✓ GROQ_API_KEY (you set this)"
echo "  ✓ DATABASE_URL (provided by Render PostgreSQL)"
echo "  ✓ REDIS_URL (provided by Render Redis)"
echo "  ✓ PORT (automatically set by Render)"
echo "  ✓ CORS_ORIGINS (update to your Netlify domain)"
echo ""
echo "Required for Netlify:"
echo "  ✓ VITE_API_URL (set to your Render backend URL)"

# Step 6: Deployment Instructions
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL CHECKS PASSED - READY TO DEPLOY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 NEXT STEPS:"
echo ""
echo "1️⃣  DEPLOY BACKEND TO RENDER:"
echo "   ├─ Go to https://dashboard.render.com"
echo "   ├─ New → Web Service"
echo "   ├─ Connect your Git repo"
echo "   ├─ Settings:"
echo "   │  ├─ Build: pip install -r requirements.txt"
echo "   │  ├─ Start: uvicorn api_gateway.main:app --host 0.0.0.0 --port \$PORT"
echo "   │  └─ Plan: Starter (\$5/month)"
echo "   └─ Set Environment Variables:"
echo "      ├─ GROQ_API_KEY=your-key"
echo "      ├─ DATABASE_URL=postgresql://... (from Render)"
echo "      ├─ REDIS_URL=redis://... (from Render)"
echo "      ├─ CORS_ORIGINS=https://yourdomain.netlify.app"
echo "      └─ Deploy"
echo ""
echo "2️⃣  DEPLOY FRONTEND TO NETLIFY:"
echo "   ├─ Go to https://app.netlify.com"
echo "   ├─ Import Git repo"
echo "   ├─ Settings:"
echo "   │  ├─ Base directory: frontend"
echo "   │  ├─ Build: npm install && npm run build"
echo "   │  ├─ Publish: frontend/dist"
echo "   │  └─ Environment:"
echo "   │     └─ VITE_API_URL=https://your-render-url.onrender.com"
echo "   └─ Deploy"
echo ""
echo "3️⃣  TEST:"
echo "   ├─ Visit your Netlify URL"
echo "   ├─ Upload a PDF"
echo "   ├─ Ask a question"
echo "   └─ Verify response from Groq"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
