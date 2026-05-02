#!/bin/bash
# 通义听悟 Skill 环境初始化脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 安装通义听悟 Skill 所需依赖..."
pip install -r "$SCRIPT_DIR/requirements.txt" -q

echo "✅ 依赖安装完成！"
echo ""
echo "📋 使用前请确保以下环境变量已设置："
echo "   export ALIBABA_CLOUD_ACCESS_KEY_ID=<你的 AccessKey ID>"
echo "   export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<你的 AccessKey Secret>"
echo ""
echo "🚀 运行示例："
echo "   python $SCRIPT_DIR/tingwu_transcribe.py \\"
echo "     --file-url 'https://your-file-url/audio.mp3' \\"
echo "     --app-key 'your-app-key' \\"
echo "     --output 'result.md'"
