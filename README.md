# Tingwu Transcribe (通义听悟转录)

基于阿里云通义听悟 API 的音视频离线转录工具。支持将公网可访问的音视频文件自动转录，并生成包含转录文本、说话人分离、章节速览、摘要总结和要点提炼的结构化 Markdown 文件。

本仓库同时包含一个 Claude Skill 配置文件 (`SKILL.md`)，可以将此工具集成到 Claude 作为自定义能力使用。

## 🌟 主要功能

- 🎤 **多语种识别**：支持中文、英文、粤语、日语、韩语等，也可自动检测语言。
- 👥 **说话人分离**：自动识别不同的发言人。
- 📑 **章节速览**：自动分割音视频并命名章节。
- 📋 **摘要总结**：自动生成全文摘要、发言总结和问答回顾。
- 🔑 **要点提炼**：提取关键信息和待办事项。
- 🌐 **翻译支持**：支持将结果翻译为中、英、日、韩、德、法、俄等多国语言。

## 🛠️ 安装与配置

### 1. 环境依赖
```bash
uv pip install -r requirements.txt
```

### 2. 环境变量设置
您需要配置阿里云的 AccessKey。AppKey 推荐也以环境变量方式配置，避免每次命令行重复输入：
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="<your_access_key_id>"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="<your_access_key_secret>"
export TINGWU_APP_KEY="<your_app_key>"         # 可选，代替 --app-key 参数
```

## 🚀 使用方法

基础转录任务（AppKey 通过环境变量设置，无需命令行传入）：
```bash
python tingwu_transcribe.py \
  --file-url "https://example.com/audio.mp3" \
  --language cn \
  --output "transcription_result.md"
```

也可以通过 `--app-key` 参数临时覆盖环境变量：
```bash
python tingwu_transcribe.py \
  --file-url "https://example.com/audio.mp3" \
  --app-key "<your_app_key>" \
  --language cn \
  --output "transcription_result.md"
```

带翻译的转录任务：
```bash
python tingwu_transcribe.py \
  --file-url "https://example.com/audio.mp3" \
  --app-key "<your_app_key>" \
  --language cn \
  --enable-translation en \
  --output "meeting_notes.md"
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--file-url` | 音视频文件公网 URL（**必选**，不支持本地路径） | 无 |
| `--app-key` | 通义听悟 AppKey（可通过环境变量 `TINGWU_APP_KEY` 替代） | `$TINGWU_APP_KEY` |
| `--language` | 源语言 (`cn`/`en`/`yue`/`ja`/`ko`/`auto`/`multilingual`) | `cn` |
| `--speaker-count` | 说话人数量（0=自动检测） | `0` |
| `--enable-translation` | 翻译目标语言 (`en`/`cn`/`ja`/`ko`/`de`/`fr`/`ru`) | 无（不翻译） |
| `--no-summary` | 禁用摘要总结 | 开启 |
| `--no-chapters` | 禁用章节速览 | 开启 |
| `--no-key-info` | 禁用要点提炼 | 开启 |
| `--output` | 输出 Markdown 文件路径 | `transcription_<时间戳>.md` |
| `--poll-interval` | 轮询间隔（秒） | `30` |
| `--max-wait` | 最大等待时间（秒） | `10800`（3小时） |

## ⚠️ 注意事项

1. **公网 URL**：`--file-url` 必须是公网可直接下载的 HTTP/HTTPS 链接。如果是本地文件，请先上传至阿里云 OSS 或其他可公开访问的文件服务器。
2. **异步处理**：通义听悟 API 为异步处理，脚本内置了轮询等待机制。处理时间取决于文件时长，最长不超过 3 小时。
3. **文件限制**：单个文件大小不超过 6GB，时长不超过 6 小时。

## 🤖 Claude Skill 集成
如果你想将此工具作为 Claude 的 Skill，请参考 [SKILL.md](SKILL.md) 并在 Claude 中进行配置。
