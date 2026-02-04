#!/usr/bin/env python3
"""텔레그램 알림 전송 (다중 모델 결과 비교)"""

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


def extract_sns_text(analysis: str) -> str:
    """분석 결과에서 SNS 홍보 문구만 추출합니다."""
    # SNS 홍보 문구 섹션 찾기
    markers = ["SNS 홍보 문구", "SNS 홍보", "홍보 문구", "X/스레드", "트위터"]

    lines = analysis.split("\n")
    capturing = False
    result_lines = []

    for line in lines:
        # 마커 발견 시 캡처 시작
        if any(marker in line for marker in markers):
            capturing = True
            continue

        # 다음 섹션 시작 시 캡처 종료
        if capturing and line.strip().startswith("#"):
            break

        if capturing and line.strip():
            result_lines.append(line)

    # 캡처된 내용이 있으면 반환
    if result_lines:
        return "\n".join(result_lines).strip()

    # 못 찾으면 마지막 200자 반환 (보통 SNS 문구가 마지막에 있음)
    return analysis[-300:].strip() if len(analysis) > 300 else analysis


def format_message(entry: dict) -> str:
    """텔레그램 메시지 형식으로 변환합니다."""
    analyzed_at = datetime.fromisoformat(entry["analyzed_at"])
    time_str = analyzed_at.strftime("%Y-%m-%d %H:%M")
    post_count = entry.get("post_count", 0)
    results = entry.get("results", [])

    # 기존 형식 호환 (단일 모델)
    if not results and "analysis" in entry:
        results = [{"model": entry.get("model", "unknown"), "analysis": entry["analysis"]}]

    message_parts = [
        f"📊 뽐뿌 릴레이 트렌드 ({time_str})",
        f"📝 분석 게시물: {post_count}개",
        f"🤖 모델 비교: {len(results)}개",
        "",
    ]

    for i, r in enumerate(results, 1):
        model_name = r["model"].split("/")[-1].replace(":free", "")
        sns_text = extract_sns_text(r["analysis"])

        # 마크다운 기호 제거
        sns_text = sns_text.replace("**", "").replace("*", "").replace("`", "")

        # 너무 길면 자르기
        if len(sns_text) > 500:
            sns_text = sns_text[:500] + "..."

        message_parts.append(f"━━━ {i}. {model_name} ━━━")
        message_parts.append(sns_text)
        message_parts.append("")

    return "\n".join(message_parts)


def send_telegram(message: str) -> bool:
    """텔레그램으로 메시지를 전송합니다."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # 메시지 길이 제한 (4096자)
    if len(message) > 4000:
        message = message[:4000] + "\n\n(메시지가 잘렸습니다)"

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

    entry = get_latest_analysis()
    if not entry:
        print("전송할 분석 결과가 없습니다.")
        return

    message = format_message(entry)
    print(f"메시지 길이: {len(message)}자")

    success = send_telegram(message)
    if success:
        print("알림 전송 완료")
    else:
        print("알림 전송 실패")
        exit(1)


if __name__ == "__main__":
    main()
