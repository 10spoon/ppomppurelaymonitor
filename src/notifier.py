#!/usr/bin/env python3
"""텔레그램 알림 전송"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

KST = timezone(timedelta(hours=9))


def get_latest_analysis() -> dict | None:
    """오늘의 최신 분석 결과를 가져옵니다."""
    script_dir = Path(__file__).parent.parent
    analysis_dir = script_dir / "data" / "analysis"

    today = datetime.now(KST).strftime("%Y-%m-%d")
    analysis_file = analysis_dir / f"{today}.json"

    if not analysis_file.exists():
        return None

    with open(analysis_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return None

    # 가장 최근 분석 결과
    return data[-1]


def escape_markdown(text: str) -> str:
    """텔레그램 MarkdownV2용 특수문자 이스케이프."""
    # MarkdownV2에서 이스케이프가 필요한 문자들
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_message(analysis: dict) -> str:
    """텔레그램 메시지 형식으로 변환합니다 (plain text)."""
    analyzed_at = datetime.fromisoformat(analysis["analyzed_at"])
    time_str = analyzed_at.strftime("%Y-%m-%d %H:%M")
    post_count = analysis.get("post_count", 0)
    content = analysis.get("analysis", "분석 결과 없음")

    # 텔레그램 메시지 길이 제한 (4096자)
    max_content_length = 3500
    if len(content) > max_content_length:
        content = content[:max_content_length] + "...\n\n(내용이 잘렸습니다)"

    # 마크다운 기호 제거하여 plain text로
    content = content.replace("**", "").replace("*", "").replace("`", "")

    message = f"""📊 뽐뿌 릴레이 트렌드 분석

🕐 {time_str}
📝 분석 게시물: {post_count}개

{content}"""

    return message


def send_telegram(message: str) -> bool:
    """텔레그램으로 메시지를 전송합니다."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if not response.ok:
            print(f"텔레그램 API 응답: {response.text}")
        response.raise_for_status()
        print("텔레그램 전송 성공")
        return True
    except requests.exceptions.RequestException as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def main():
    print(f"[{datetime.now(KST).isoformat()}] 텔레그램 알림 전송 시작...")

    analysis = get_latest_analysis()
    if not analysis:
        print("전송할 분석 결과가 없습니다.")
        return

    message = format_message(analysis)
    print(f"메시지 길이: {len(message)}자")

    success = send_telegram(message)
    if success:
        print("알림 전송 완료")
    else:
        print("알림 전송 실패")
        exit(1)


if __name__ == "__main__":
    main()
