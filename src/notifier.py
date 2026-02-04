#!/usr/bin/env python3
"""텔레그램 알림 전송 (모델별 개별 메시지)"""

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

    return data[-1]


def clean_text(text: str) -> str:
    """마크다운 기호를 제거합니다."""
    return text.replace("**", "").replace("*", "").replace("`", "").replace("##", "").replace("#", "")


def format_single_model_message(entry: dict, result: dict, index: int, total: int) -> str:
    """단일 모델 결과를 메시지로 변환합니다."""
    analyzed_at = datetime.fromisoformat(entry["analyzed_at"])
    time_str = analyzed_at.strftime("%H:%M")
    post_count = entry.get("post_count", 0)

    model_name = result["model"].split("/")[-1].replace(":free", "")
    analysis = clean_text(result["analysis"])

    # 너무 길면 자르기 (텔레그램 4096자 제한)
    if len(analysis) > 3500:
        analysis = analysis[:3500] + "\n\n(내용이 잘렸습니다)"

    message = f"""📊 [{index}/{total}] {model_name}
🕐 {time_str} | 📝 {post_count}개 게시물 분석

{analysis}"""

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
        return True
    except requests.exceptions.RequestException as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def main():
    print(f"[{datetime.now(KST).isoformat()}] 텔레그램 알림 전송 시작...")

    entry = get_latest_analysis()
    if not entry:
        print("전송할 분석 결과가 없습니다.")
        return

    results = entry.get("results", [])

    # 기존 형식 호환 (단일 모델)
    if not results and "analysis" in entry:
        results = [{"model": entry.get("model", "unknown"), "analysis": entry["analysis"]}]

    if not results:
        print("전송할 결과가 없습니다.")
        return

    total = len(results)
    success_count = 0

    for i, result in enumerate(results, 1):
        message = format_single_model_message(entry, result, i, total)
        print(f"\n[{i}/{total}] {result['model']} 전송 중... ({len(message)}자)")

        if send_telegram(message):
            print(f"  ✓ 전송 성공")
            success_count += 1
        else:
            print(f"  ✗ 전송 실패")

    print(f"\n알림 전송 완료: {success_count}/{total}")

    if success_count == 0:
        exit(1)


if __name__ == "__main__":
    main()
