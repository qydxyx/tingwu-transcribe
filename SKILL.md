---
name: tingwu-transcribe
description: "使用阿里云通义听悟 API 对音视频文件（URL）进行离线转录，自动生成包含转录文本、说话人分离、章节速览、摘要总结和要点提炼的 Markdown 文件。当用户提到要转录音频/视频、提取会议纪要、生成字幕文本时使用此 Skill。"
allowed-tools: [Bash, Read, Write]
---

# 通义听悟转录 Skill

## 功能概述

调用阿里云通义听悟 API 对音视频文件进行离线转录，并将结果整理为结构化 Markdown 文件。

**支持的能力：**
- 🎤 语音转文字（中/英/粤/日/韩/多语种）
- 👥 说话人自动分离标注
- 📑 章节速览（自动分割并命名章节）
- 📋 全文摘要 / 发言总结 / 问答回顾
- 🔑 关键词提取 / 待办事项识别
- 🌐 翻译（中英日韩德法俄）

**支持的格式：** mp3、wav、m4a、mp4、mov、mkv、webm、flv、aac、ogg、flac 等

---

## 使用前提

### 必须的环境变量

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=<你的 AccessKey ID>
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<你的 AccessKey Secret>
```

### 必须的参数

- `--file-url`：音视频文件的**公网可访问** HTTP/HTTPS URL（不支持本地文件路径）
- `--app-key`：在[通义听悟管控台](https://nls-portal.console.aliyun.com/tingwu/projects)创建的 AppKey

---

## 调用流程

当用户要求转录音视频文件时，按以下步骤操作：

### 第一步：确认必要信息

向用户确认以下信息（若已在对话中提供则跳过）：

1. **音视频文件 URL**（必须是公网可访问的 HTTP/HTTPS 链接）
   - 如果用户提供的是本地路径，告知需要先上传到 OSS 或其他文件服务器获取公网链接
2. **AppKey**（如果用户未提供，提示其从通义听悟管控台获取）
3. **语言**（默认中文 cn，可选：cn/en/yue/ja/ko/auto/multilingual）
4. **输出文件名**（可选，默认自动生成带时间戳的文件名）
5. **是否需要翻译**（可选，如需翻译说明目标语言）

### 第二步：检查依赖

```bash
SKILL_DIR="$HOME/.claude/skills/tingwu-transcribe"
pip show aliyun-python-sdk-core > /dev/null 2>&1 || pip install -r "$SKILL_DIR/requirements.txt" -q
```

### 第三步：运行转录脚本

基础用法（使用用户提供的参数）：

```bash
python "$HOME/.claude/skills/tingwu-transcribe/tingwu_transcribe.py" \
  --file-url "<用户提供的 URL>" \
  --app-key "<用户提供的 AppKey>" \
  --language cn \
  --output "<输出文件名>.md"
```

带翻译的用法：

```bash
python "$HOME/.claude/skills/tingwu-transcribe/tingwu_transcribe.py" \
  --file-url "<URL>" \
  --app-key "<AppKey>" \
  --language cn \
  --enable-translation en \
  --output meeting_notes.md
```

### 第四步：报告结果

转录完成后：
1. 告知用户 Markdown 文件保存的完整路径
2. 读取生成的 Markdown 文件，在对话中展示摘要部分（如果存在）
3. 询问用户是否需要进一步处理（如格式调整、内容分析等）

---

## 参数参考

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--file-url` | 音视频文件公网 URL（必选） | — |
| `--app-key` | 通义听悟 AppKey（必选） | — |
| `--language` | 源语言：cn/en/yue/ja/ko/auto/multilingual | `cn` |
| `--speaker-count` | 说话人数量（0=自动检测） | `0` |
| `--enable-translation` | 翻译目标语言（en/cn/ja/ko/de/fr/ru） | 不翻译 |
| `--no-summary` | 禁用摘要总结 | 默认开启 |
| `--no-chapters` | 禁用章节速览 | 默认开启 |
| `--no-key-info` | 禁用要点提炼 | 默认开启 |
| `--output` | 输出 Markdown 文件路径 | `transcription_<时间戳>.md` |
| `--poll-interval` | 轮询间隔（秒） | `30` |
| `--max-wait` | 最大等待时间（秒） | `10800`（3小时） |

---

## 注意事项

- **任务处理时间**：通义听悟为异步处理，通常在几分钟内完成，最长 3 小时
- **文件 URL 要求**：必须是公网可直接下载的链接，不支持 IP 地址、包含空格的 URL
- **文件大小限制**：≤ 6GB，时长 ≤ 6 小时
- **结果有效期**：结果下载链接有效期为 30 天
- **QPS 限制**：创建任务 20 QPS，查询任务 100 QPS（脚本已内置自动退避）

---

## 常见问题处理

**Q: 用户提供的是本地文件路径怎么办？**

提示用户：
```
通义听悟 API 不支持直接上传本地文件，需要先将文件上传到可公网访问的服务器。
推荐方式：
1. 上传到阿里云 OSS 并获取公开访问 URL
2. 上传到其他文件服务器（如 GitHub Releases、OneDrive 等）
```

**Q: 转录结果为空怎么办？**

可能原因：音视频文件中无有效人声、背景噪音过多。建议用户检查原始文件。

**Q: 如何查询已提交任务的状态？**

TaskId 会在脚本输出中显示。可以直接运行以下命令查询：
```bash
python "$HOME/.claude/skills/tingwu-transcribe/tingwu_transcribe.py" --help
```
目前脚本不支持单独查询已有 TaskId，若需要此功能请告知用户联系开发者扩展功能。
