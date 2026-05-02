#!/usr/bin/env python3
# 兼容 Python 3.9+
# -*- coding: utf-8 -*-
"""
通义听悟离线转录脚本
调用阿里云通义听悟 API，对音视频文件进行转录并生成 Markdown 输出。

使用前请确保设置以下环境变量：
  ALIBABA_CLOUD_ACCESS_KEY_ID
  ALIBABA_CLOUD_ACCESS_KEY_SECRET
  TINGWU_APP_KEY          （可选，用于代替 --app-key 命令行参数）

用法：
  python tingwu_transcribe.py --file-url <URL> [--app-key <AppKey>] [options]
"""

import argparse
import json
import os
import sys
import time
import datetime
import requests
from typing import Optional, Dict, Any

try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.request import CommonRequest
    from aliyunsdkcore.auth.credentials import AccessKeyCredential
except ImportError:
    print("❌ 缺少依赖：aliyun-python-sdk-core")
    print("   请运行：uv pip install aliyun-python-sdk-core")
    sys.exit(1)


# ─── 常量 ───────────────────────────────────────────────────────────────────

TINGWU_DOMAIN = "tingwu.cn-beijing.aliyuncs.com"
TINGWU_VERSION = "2023-09-30"
TINGWU_TASK_PATH = "/openapi/tingwu/v2/tasks"


# ─── API 工具函数 ────────────────────────────────────────────────────────────

def build_client() -> AcsClient:
    """从环境变量构建 AcsClient。"""
    ak_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
    ak_secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    if not ak_id or not ak_secret:
        print("❌ 未找到阿里云凭证，请设置环境变量：")
        print("   export ALIBABA_CLOUD_ACCESS_KEY_ID=<你的 AccessKey ID>")
        print("   export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<你的 AccessKey Secret>")
        sys.exit(1)
    credentials = AccessKeyCredential(ak_id, ak_secret)
    return AcsClient(region_id="cn-beijing", credential=credentials)


def make_request(method: str, uri: str) -> CommonRequest:
    """创建基础 CommonRequest 对象。"""
    req = CommonRequest()
    req.set_accept_format("json")
    req.set_domain(TINGWU_DOMAIN)
    req.set_version(TINGWU_VERSION)
    req.set_protocol_type("https")
    req.set_method(method)
    req.set_uri_pattern(uri)
    req.add_header("Content-Type", "application/json")
    return req


def create_task(client: AcsClient, args: argparse.Namespace) -> str:
    """
    提交离线转写任务，返回 TaskId。
    """
    body = {
        "AppKey": args.app_key,
        "Input": {
            "FileUrl": args.file_url,
            "SourceLanguage": args.language,
            "TaskKey": "task_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        },
        "Parameters": {},
    }

    params = body["Parameters"]

    # 语音识别 / 说话人分离
    transcription = {"DiarizationEnabled": True}
    diarization = {"SpeakerCount": args.speaker_count}
    transcription["Diarization"] = diarization
    params["Transcription"] = transcription

    # 章节速览
    if args.enable_chapters:
        params["AutoChaptersEnabled"] = True

    # 要点提炼
    if args.enable_key_info:
        params["MeetingAssistanceEnabled"] = True
        params["MeetingAssistance"] = {"Types": ["Actions", "KeyInformation"]}

    # 摘要总结
    if args.enable_summary:
        params["SummarizationEnabled"] = True
        params["Summarization"] = {
            "Types": ["Paragraph", "Conversational", "QuestionsAnswering"]
        }

    # 翻译
    if args.enable_translation:
        params["TranslationEnabled"] = True
        params["Translation"] = {"TargetLanguages": [args.enable_translation]}

    # 口语书面化
    params["TextPolishEnabled"] = True

    req = make_request("PUT", TINGWU_TASK_PATH)
    req.add_query_param("type", "offline")
    req.set_content(json.dumps(body).encode("utf-8"))

    print(f"🚀 正在提交转录任务...")
    print(f"   文件 URL : {args.file_url}")
    print(f"   识别语言 : {args.language}")

    try:
        response = client.do_action_with_exception(req)
        result = json.loads(response)
    except Exception as e:
        print(f"❌ 提交任务失败：{e}")
        sys.exit(1)

    if result.get("Code") != "0":
        print(f"❌ API 返回错误：{result.get('Message', '未知错误')}")
        sys.exit(1)

    task_id = result["Data"]["TaskId"]
    print(f"✅ 任务已提交，TaskId: {task_id}")
    return task_id


def poll_task(client: AcsClient, task_id: str, poll_interval: int, max_wait: int) -> dict:
    """
    轮询查询任务状态，直到完成或超时。
    返回任务结果数据。
    """
    uri = f"{TINGWU_TASK_PATH}/{task_id}"
    start_time = time.time()
    attempt = 0

    print(f"\n⏳ 等待转录完成（每 {poll_interval}s 查询一次，最长等待 {max_wait//60} 分钟）...")

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"\n❌ 超过最大等待时间（{max_wait}s），任务可能仍在队列中。")
            print(f"   您可以稍后使用以下命令查询：TaskId = {task_id}")
            sys.exit(1)

        # 指数退避：前几次较快，之后稳定
        if attempt > 0:
            wait = min(poll_interval * (1.5 ** min(attempt - 1, 4)), poll_interval * 8)
            wait = int(wait)
            for i in range(wait, 0, -1):
                print(f"\r   [{int(elapsed):>5}s elapsed] 下次查询倒计时: {i:>3}s  ", end="", flush=True)
                time.sleep(1)
                elapsed = time.time() - start_time
            print()

        attempt += 1
        req = make_request("GET", uri)
        try:
            response = client.do_action_with_exception(req)
            result = json.loads(response)
        except Exception as e:
            print(f"   ⚠️  查询失败（将重试）：{e}")
            continue

        data = result.get("Data", {})
        status = data.get("TaskStatus", "UNKNOWN")

        elapsed_str = _fmt_duration(int(elapsed * 1000))
        print(f"   [{elapsed_str} elapsed] 状态: {status}")

        if status == "COMPLETED":
            print("✅ 转录完成！")
            return data
        elif status == "FAILED":
            err_code = data.get("ErrorCode", "")
            err_msg = data.get("ErrorMessage", "")
            print(f"❌ 任务失败：[{err_code}] {err_msg}")
            sys.exit(1)
        # ONGOING 或 INVALID → 继续等待


def download_result_json(url: str, label: str) -> Optional[Dict[str, Any]]:
    """从 URL 下载并解析 JSON 结果文件。"""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"   ⚠️  下载 {label} 失败：{e}")
        return None


# ─── Markdown 生成 ───────────────────────────────────────────────────────────

def _fmt_duration(ms: int) -> str:
    """将毫秒格式化为 HH:MM:SS 字符串。"""
    total_sec = ms // 1000
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _ms_to_timestamp(ms: int) -> str:
    """将毫秒转为带方括号的时间戳，如 [01:23]。"""
    return f"[{_fmt_duration(ms)}]"


def _build_transcription_section(transcription_data: dict) -> str:
    """从转录 JSON 构建 Markdown 转录文本段落。"""
    paragraphs = transcription_data.get("Transcription", {}).get("Paragraphs", [])
    audio_info = transcription_data.get("Transcription", {}).get("AudioInfo", {})

    if not paragraphs:
        return "_（无转录文本）_\n"

    lines = []
    last_speaker = None

    for para in paragraphs:
        speaker_id = para.get("SpeakerId", "0")
        words = para.get("Words", [])
        if not words:
            continue

        # 按 SentenceId 分组
        sentences: dict[int, list] = {}
        for w in words:
            sid = w.get("SentenceId", 0)
            sentences.setdefault(sid, []).append(w)

        for sid in sorted(sentences.keys()):
            s_words = sentences[sid]
            text = "".join(w.get("Text", "") for w in s_words)
            start_ms = s_words[0].get("Start", 0)
            ts = _ms_to_timestamp(start_ms)

            speaker_label = f"说话人 {speaker_id}" if speaker_id else "说话人"

            # 说话人切换时加标题
            if speaker_label != last_speaker:
                lines.append(f"\n**{speaker_label}** {ts}")
                last_speaker = speaker_label
            else:
                lines.append(f"_{ts}_")

            lines.append(f"{text}\n")

    return "\n".join(lines)


def _build_chapters_section(chapters_data: dict) -> str:
    """从章节速览 JSON 构建 Markdown 章节段落。"""
    chapters = chapters_data.get("AutoChapters", {}).get("Chapters", [])
    if not chapters:
        return "_（无章节信息）_\n"

    lines = []
    for i, ch in enumerate(chapters, 1):
        title = ch.get("Headline", f"第 {i} 章")
        summary = ch.get("Summary", "")
        start_ms = ch.get("Start", 0)
        end_ms = ch.get("End", 0)
        ts_range = f"{_ms_to_timestamp(start_ms)} → {_ms_to_timestamp(end_ms)}"
        lines.append(f"### {i}. {title}  `{ts_range}`")
        if summary:
            lines.append(f"{summary}\n")
    return "\n".join(lines)


def _build_summarization_section(summ_data: dict) -> str:
    """从摘要总结 JSON 构建 Markdown 摘要段落。"""
    summaries = summ_data.get("Summarization", {}).get("Summaries", [])
    if not summaries:
        return "_（无摘要信息）_\n"

    type_labels = {
        "Paragraph": "全文摘要",
        "Conversational": "发言总结",
        "QuestionsAnswering": "问答回顾",
        "MindMap": "思维导图",
    }

    lines = []
    for s in summaries:
        s_type = s.get("SummaryType", "")
        content = s.get("Summary", "").strip()
        label = type_labels.get(s_type, s_type)
        if content:
            lines.append(f"#### {label}")
            lines.append(f"{content}\n")
    return "\n".join(lines) if lines else "_（无摘要信息）_\n"


def _build_meeting_assistance_section(ma_data: dict) -> str:
    """从要点提炼 JSON 构建 Markdown 要点段落。"""
    items = ma_data.get("MeetingAssistance", {}).get("ActionItems", [])
    keywords = ma_data.get("MeetingAssistance", {}).get("KeyInformation", {})

    lines = []

    # 关键词
    kw_list = keywords.get("Keywords", [])
    if kw_list:
        kws = "、".join(kw_list)
        lines.append(f"**关键词**：{kws}\n")

    # 重点内容
    key_points = keywords.get("KeyPoints", [])
    if key_points:
        lines.append("**重点内容**：")
        for kp in key_points:
            lines.append(f"- {kp}")
        lines.append("")

    # 待办事项
    if items:
        lines.append("**待办事项**：")
        for item in items:
            content = item.get("Content", "")
            if content:
                lines.append(f"- [ ] {content}")
        lines.append("")

    return "\n".join(lines) if lines else "_（无要点信息）_\n"


def _build_translation_section(trans_data: dict, target_lang: str) -> str:
    """从翻译 JSON 构建 Markdown 翻译段落。"""
    paragraphs = trans_data.get("Translation", {}).get("Paragraphs", [])
    if not paragraphs:
        return "_（无翻译内容）_\n"

    lines = []
    last_speaker = None
    for para in paragraphs:
        speaker_id = para.get("SpeakerId", "0")
        words = para.get("Words", [])
        if not words:
            continue

        # 按 SentenceId 分组
        sentences: dict[int, list] = {}
        for w in words:
            sid = w.get("SentenceId", 0)
            sentences.setdefault(sid, []).append(w)

        for sid in sorted(sentences.keys()):
            s_words = sentences[sid]
            text = " ".join(w.get("Text", "") for w in s_words).strip()
            start_ms = s_words[0].get("Start", 0)
            ts = _ms_to_timestamp(start_ms)
            speaker_label = f"说话人 {speaker_id}" if speaker_id else "说话人"

            if speaker_label != last_speaker:
                lines.append(f"\n**{speaker_label}** {ts}")
                last_speaker = speaker_label
            lines.append(f"{text}\n")

    return "\n".join(lines)


def generate_markdown(
    task_id: str,
    args: argparse.Namespace,
    task_data: dict,
    results: dict,
) -> str:
    """
    整合所有结果，生成完整 Markdown 字符串。
    results 是 { key: parsed_json_dict } 的字典。
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 音频基础信息
    transcription_json = results.get("Transcription", {})
    audio_info = transcription_json.get("Transcription", {}).get("AudioInfo", {})
    duration_ms = audio_info.get("Duration", 0)
    duration_str = _fmt_duration(duration_ms) if duration_ms else "未知"
    detected_lang = audio_info.get("Language", args.language)

    lang_map = {
        "cn": "中文", "en": "英文", "yue": "粤语",
        "ja": "日语", "ko": "韩语", "auto": "自动检测",
        "multilingual": "多语种",
    }
    lang_label = lang_map.get(detected_lang, detected_lang)

    sections = []

    # ── 封面信息 ──────────────────────────────────────────────────────────────
    sections.append(f"""# 音视频转录记录

> **文件 URL**：{args.file_url}
> **音频时长**：{duration_str}
> **识别语言**：{lang_label}
> **TaskId**：`{task_id}`
> **转录时间**：{now}

---""")

    # ── 摘要总结 ──────────────────────────────────────────────────────────────
    if args.enable_summary and "Summarization" in results:
        sections.append("## 📋 摘要总结\n")
        sections.append(_build_summarization_section(results["Summarization"]))
        sections.append("---")

    # ── 章节速览 ──────────────────────────────────────────────────────────────
    if args.enable_chapters and "AutoChapters" in results:
        sections.append("## 📑 章节速览\n")
        sections.append(_build_chapters_section(results["AutoChapters"]))
        sections.append("---")

    # ── 要点提炼 ──────────────────────────────────────────────────────────────
    if args.enable_key_info and "MeetingAssistance" in results:
        sections.append("## 🔑 要点提炼\n")
        sections.append(_build_meeting_assistance_section(results["MeetingAssistance"]))
        sections.append("---")

    # ── 转录文本 ──────────────────────────────────────────────────────────────
    sections.append("## 💬 转录文本\n")
    if "Transcription" in results:
        sections.append(_build_transcription_section(transcription_json))
    else:
        sections.append("_（转录结果暂不可用）_")

    # ── 翻译结果 ──────────────────────────────────────────────────────────────
    if args.enable_translation and "Translation" in results:
        lang_label_map = {
            "en": "English", "cn": "中文", "ja": "日本語",
            "ko": "한국어", "de": "Deutsch", "fr": "Français", "ru": "Русский",
        }
        tgt = lang_label_map.get(args.enable_translation, args.enable_translation.upper())
        sections.append(f"\n---\n\n## 🌐 翻译（{tgt}）\n")
        sections.append(_build_translation_section(results["Translation"], args.enable_translation))

    return "\n\n".join(sections)


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="通义听悟离线音视频转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基础转录（中文）
  python tingwu_transcribe.py \\
    --file-url 'https://example.com/audio.mp3' \\
    --app-key 'your-app-key'

  # 转录 + 翻译成英文 + 指定输出路径
  python tingwu_transcribe.py \\
    --file-url 'https://example.com/meeting.mp4' \\
    --app-key 'your-app-key' \\
    --language cn \\
    --enable-translation en \\
    --output meeting_notes.md

  # 自动语言检测 + 禁用章节速览
  python tingwu_transcribe.py \\
    --file-url 'https://example.com/audio.wav' \\
    --app-key 'your-app-key' \\
    --language auto \\
    --no-chapters

环境变量：
  ALIBABA_CLOUD_ACCESS_KEY_ID       阿里云 AccessKey ID（必须）
  ALIBABA_CLOUD_ACCESS_KEY_SECRET   阿里云 AccessKey Secret（必须）
  TINGWU_APP_KEY                    通义听悟 AppKey（可选，代替 --app-key）
        """,
    )

    # 必选参数
    parser.add_argument("--file-url", required=True,
                        help="音视频文件的公网 HTTP/HTTPS URL（必须可公开访问）")
    parser.add_argument("--app-key", default=None,
                        help="通义听悟管控台创建的 AppKey（也可通过环境变量 TINGWU_APP_KEY 设置）")

    # 识别参数
    parser.add_argument("--language", default="cn",
                        choices=["cn", "en", "yue", "ja", "ko", "auto", "multilingual"],
                        help="音频源语言（默认: cn）")
    parser.add_argument("--speaker-count", type=int, default=0,
                        help="说话人数量，0=自动检测（默认: 0）")

    # AI 功能开关
    parser.add_argument("--enable-translation", metavar="LANG",
                        help="翻译目标语言，如 en/cn/ja/ko/de/fr/ru（默认: 不翻译）")
    parser.add_argument("--no-summary", dest="enable_summary",
                        action="store_false", help="禁用摘要总结")
    parser.add_argument("--no-chapters", dest="enable_chapters",
                        action="store_false", help="禁用章节速览")
    parser.add_argument("--no-key-info", dest="enable_key_info",
                        action="store_false", help="禁用要点提炼")
    parser.set_defaults(enable_summary=True, enable_chapters=True, enable_key_info=True)

    # 输出参数
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    parser.add_argument("--output", default=f"transcription_{timestamp}.md",
                        help="输出 Markdown 文件路径（默认: transcription_<timestamp>.md）")

    # 轮询参数
    parser.add_argument("--poll-interval", type=int, default=30,
                        help="首次轮询间隔（秒，默认: 30）")
    parser.add_argument("--max-wait", type=int, default=10800,
                        help="最大等待时间（秒，默认: 10800 = 3小时）")

    args = parser.parse_args()

    # 若未通过命令行传入 --app-key，则尝试从环境变量读取
    if not args.app_key:
        args.app_key = os.environ.get("TINGWU_APP_KEY")
    if not args.app_key:
        print("❌ 未指定 AppKey，请通过 --app-key 参数或环境变量 TINGWU_APP_KEY 设置。")
        print("   export TINGWU_APP_KEY=<你的 AppKey>")
        sys.exit(1)

    # 构建客户端
    client = build_client()

    # 1. 提交任务
    task_id = create_task(client, args)

    # 2. 轮询任务
    task_data = poll_task(client, task_id, args.poll_interval, args.max_wait)

    # 3. 下载并解析结果
    result_urls = task_data.get("Result", {})
    results = {}

    result_keys = [
        "Transcription", "AutoChapters", "Summarization",
        "MeetingAssistance", "Translation",
    ]

    print("\n📥 正在下载转录结果...")
    for key in result_keys:
        url = result_urls.get(key)
        if url:
            print(f"   下载 {key}...")
            parsed = download_result_json(url, key)
            if parsed:
                results[key] = parsed

    if not results:
        print("❌ 未能下载任何结果文件。")
        sys.exit(1)

    # 4. 生成 Markdown
    print("\n📝 生成 Markdown 文件...")
    md_content = generate_markdown(task_id, args, task_data, results)

    # 5. 写入文件
    output_path = os.path.abspath(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n✅ 完成！Markdown 已保存至：")
    print(f"   {output_path}")
    print()

    # 打印简要摘要
    if "Summarization" in results:
        summaries = results["Summarization"].get("Summarization", {}).get("Summaries", [])
        for s in summaries:
            if s.get("SummaryType") == "Paragraph":
                content = s.get("Summary", "").strip()
                if content:
                    print("📋 全文摘要（预览）：")
                    preview = content[:300]
                    if len(content) > 300:
                        preview += "..."
                    print(f"   {preview}")
                    print()
                break


if __name__ == "__main__":
    main()
