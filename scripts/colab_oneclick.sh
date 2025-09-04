#!/bin/bash

# colab_oneclick.sh - One-click setup and execution for Colab environment
# Owner-run only: This script sets up the environment and launches the generation pipeline

set -e

echo "🚀 Colab One-Click Setup Starting..."
echo "================================="

# Configuration
REPO_URL="https://github.com/Atomheart-Father/llm-active-questioning.git"
BRANCH="main"
PROJECT_DIR="llm-active-questioning"
DATE=$(date +%Y-%m-%d)
ENV_TEMPLATE=".env.template"

# Step 1: Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-dev \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Step 2: Clone repository
echo "📥 Cloning repository..."
if [ ! -d "$PROJECT_DIR" ]; then
    git clone -b "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
else
    echo "Repository already exists, pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull origin "$BRANCH"
    cd ..
fi

cd "$PROJECT_DIR"

# Step 3: Create .env template
echo "📝 Creating .env template..."
cat > "$ENV_TEMPLATE" << 'EOF'
# LLM Active Questioning - Environment Configuration
# Copy this file to .env and fill in your API keys
# DO NOT commit .env to version control

# Gemini API Keys (required for all tasks)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_API_KEY2=your_gemini_api_key2_here
GEMINI_API_KEY3=your_gemini_api_key3_here

# DeepSeek API Keys (required for fallback and RSD tasks)
DeepSeek_API_KEY=your_deepseek_api_key_here
DeepSeek_API_KEY2=your_deepseek_api_key2_here

# Generation Configuration (do not modify unless instructed)
IDLE_TIMEOUT_S=90
READ_TIMEOUT_S=240
CONNECT_TIMEOUT_S=10
ALLOW_RSD_FALLBACK=true
MAX_CONCURRENCY=4

# Output Limits
ALC_MAX_TOKENS=768
RSD_MAX_TOKENS=1024
AR_MAX_TOKENS=1536
EOF

if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Please copy $ENV_TEMPLATE to .env and fill in your API keys:"
    echo "cp $ENV_TEMPLATE .env"
    echo "Then edit .env with your actual API keys"
    exit 1
fi

# Step 4: Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Verify environment
echo "🔍 Verifying environment setup..."
python3 -c "
import sys
sys.path.append('.')
try:
    from streaming_client import LLMClient
    print('✓ streaming_client.py - OK')
except ImportError as e:
    print(f'✗ streaming_client.py - Error: {e}')
    sys.exit(1)

try:
    from schema_validator import validate_schema, minimal_completion, extract_largest_json
    print('✓ schema_validator.py - OK')
except ImportError as e:
    print(f'✗ schema_validator.py - Error: {e}')
    sys.exit(1)

try:
    import os
    env_keys = ['GEMINI_API_KEY', 'DeepSeek_API_KEY']
    missing = [k for k in env_keys if not os.getenv(k)]
    if missing:
        print(f'✗ Missing environment variables: {missing}')
        sys.exit(1)
    print('✓ Environment variables - OK')
except Exception as e:
    print(f'✗ Environment check failed: {e}')
    sys.exit(1)
"

# Step 6: Create necessary directories
echo "📁 Creating output directories..."
mkdir -p "data/gen/$DATE"
mkdir -p "runs/$DATE"
mkdir -p "artifacts_review"
mkdir -p "artifacts_review/samples"

# Step 7: Launch generation
echo "🚀 Launching colab_entry.py..."
echo "Date: $DATE"
echo "Targets: ALC=4, AR=3, RSD=3"
echo "================================="

python3 colab_entry.py

# Step 8: Show results
echo "📊 Generation complete!"
echo "Check artifacts_review/ for results:"
ls -la artifacts_review/

echo "✅ Colab One-Click Setup Complete!"
echo "Next steps:"
echo "1. Review artifacts_review/ contents"
echo "2. Commit only artifacts_review/** for submission"
