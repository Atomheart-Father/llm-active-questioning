#!/bin/bash
# 加载环境变量（从.env文件）
# 注意：.env文件包含敏感信息，不要提交git

if [ -f ".env" ]; then
    echo "📝 加载环境变量从 .env 文件..."
    export $(grep -v '^#' .env | xargs)
    echo "✅ 环境变量已加载"
    
    # 验证必要变量
    if [ -z "$RUN_MODE" ]; then
        echo "❌ 缺少 RUN_MODE"
        exit 1
    fi
    
    if [ -z "$SCORER_PROVIDER" ]; then
        echo "❌ 缺少 SCORER_PROVIDER"
        exit 1
    fi
    
    # 检查对应的API密钥
    IFS=',' read -ra PROVIDERS <<< "$SCORER_PROVIDER"
    for provider in "${PROVIDERS[@]}"; do
        provider=$(echo "$provider" | xargs) # trim whitespace
        case $provider in
            "deepseek_r1")
                if [ -z "$DEEPSEEK_API_KEY" ]; then
                    echo "❌ SCORER_PROVIDER包含deepseek_r1但缺少DEEPSEEK_API_KEY"
                    exit 1
                fi
                ;;
            "gemini")
                if [ -z "$GEMINI_API_KEY" ]; then
                    echo "❌ SCORER_PROVIDER包含gemini但缺少GEMINI_API_KEY"
                    exit 1
                fi
                ;;
            "gpt35")
                if [ -z "$OPENAI_API_KEY" ]; then
                    echo "❌ SCORER_PROVIDER包含gpt35但缺少OPENAI_API_KEY"
                    exit 1
                fi
                ;;
        esac
    done
    
    echo "✅ 所有必要的API密钥已验证"
else
    echo "❌ 未找到 .env 文件"
    echo "请创建 .env 文件，包含："
    echo "RUN_MODE=prod"
    echo "SCORER_PROVIDER=deepseek_r1"  # 或 gemini,deepseek_r1 等
    echo "DEEPSEEK_API_KEY=sk-xxxx"
    echo "GEMINI_API_KEY=AIza-xxxx"
    exit 1
fi
