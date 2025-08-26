#!/usr/bin/env bash
set -euo pipefail

# ========= 用户可传的变量（留空就用默认） =========
REPO_URL="${REPO_URL:-}"            # 例：https://github.com/你的账户/你的仓库.git
BRANCH="${BRANCH:-main}"
WORKDIR="${WORKDIR:-/content}"      # Colab 的工作目录
DRIVE_DIR="${DRIVE_DIR:-/content/drive/MyDrive/llm-aq}"  # 存放日志/ckpt的位置
PROJECT_DIR="${PROJECT_DIR:-$WORKDIR/repo}"  # 仓库拉取到这里
PYTHON="${PYTHON:-python}"

echo "==> Colab bootstrap starting..."
echo "REPO_URL=${REPO_URL:-<unset>}"
echo "BRANCH=$BRANCH"
echo "WORKDIR=$WORKDIR"
echo "DRIVE_DIR=$DRIVE_DIR"
echo "PROJECT_DIR=$PROJECT_DIR"

# ========= 1) 基础依赖 =========
echo "==> Upgrade pip & install base deps"
$PYTHON -m pip -q install --upgrade pip wheel setuptools
sudo apt-get -qq update || true
sudo apt-get -qq install -y git-lfs || true
git lfs install || true

# ========= 2) 判断是否在 Colab，尝试挂载 Google Drive =========
if [ -d "/content" ]; then
  echo "==> Detected Colab environment. Mounting Google Drive..."
  $PYTHON - <<'PY'
try:
    from google.colab import drive
    drive.mount("/content/drive")
    print("Drive mounted at /content/drive")
except Exception as e:
    print("WARNING: Drive mount failed:", e)
PY
else
  echo "==> Not in Colab (/content not found). Skipping Drive mount."
fi

# ========= 3) 准备目录 =========
mkdir -p "$DRIVE_DIR"/{logs,checkpoints,reports,artifacts} || true
mkdir -p "$WORKDIR" "$PROJECT_DIR"

# ========= 4) 克隆/更新仓库 =========
if [ -z "${REPO_URL}" ]; then
  echo "ERROR: REPO_URL 未设置。示例："
  echo '  REPO_URL="https://github.com/你的账户/你的仓库.git"'
  exit 2
fi
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "==> Repo exists. Pull latest..."
  cd "$PROJECT_DIR"
  git fetch --all -q
  git checkout "$BRANCH" -q
  git pull --rebase -q
else
  echo "==> Cloning repo..."
  cd "$WORKDIR"
  git clone -q --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
  cd "$PROJECT_DIR"
fi

# ========= 5) 安装 Python 依赖 =========
REQ_FILE="ops/colab/requirements-colab.txt"
if [ -f "$REQ_FILE" ]; then
  echo "==> Installing deps from $REQ_FILE"
  $PYTHON -m pip -q install -r "$REQ_FILE"
else
  echo "WARNING: $REQ_FILE not found. Installing a safe default set..."
  $PYTHON -m pip -q install 'torch>=2.3' 'transformers>=4.43' 'accelerate>=0.30' \
    'trl>=0.9' 'peft>=0.11' 'datasets>=2.19' 'evaluate>=0.4' 'tqdm' 'numpy' \
    'scikit-learn' 'pyyaml' 'jsonlines' 'psutil' 'pytest'
fi

# ========= 6) 写入 env.sh（从模板复制，再叠加用户传入的密钥） =========
ENV_DIR="$DRIVE_DIR/env"
mkdir -p "$ENV_DIR"
ENV_FILE="$ENV_DIR/env.sh"
if [ ! -f "$ENV_FILE" ]; then
  echo "==> Creating env.sh from template"
  if [ -f "ops/colab/env.template.sh" ]; then
    cp ops/colab/env.template.sh "$ENV_FILE"
  else
    cat > "$ENV_FILE" <<'EOS'
export RUN_MODE=prod
export BASE_MODEL="Qwen/Qwen3-4B-Thinking-2507"
export SCORER_PROVIDER="deepseek_r1"
export SCORER_API_KEY=""   # <-- 在Google Drive里填上真实Key
EOS
  fi
fi

# 若用户在启动命令中传了 SCORER_API_KEY，就追加/更新
if [ "${SCORER_API_KEY:-}" != "" ]; then
  sed -i '/SCORER_API_KEY/d' "$ENV_FILE"
  echo "export SCORER_API_KEY=\"$SCORER_API_KEY\"" >> "$ENV_FILE"
fi

echo "==> Using env file at: $ENV_FILE"
echo "内容预览："
grep -v API_KEY "$ENV_FILE" || true
echo "(已隐藏 SCORER_API_KEY)"

# ========= 7) 快速自检 =========
echo "==> Running smoke check"
$PYTHON ops/colab/smoke_check.py --drive "$DRIVE_DIR" || true

echo "==> Bootstrap done."
echo ""
echo "下一步推荐："
echo "  1) 运行预检：!bash ops/colab/preflight.sh"
echo "  2) 开始试训：!bash ops/colab/run_rc1.sh"
echo "  3) 断点续训：!bash ops/colab/resume_latest.sh"
