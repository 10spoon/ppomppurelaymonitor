#!/usr/bin/env python3
"""AI 기반 트렌드 분석기"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

KST = timezone(timedelta(hours=9))


def load_recent_data(hours: int = 24) -> list[dict]:
    """최근 N시간 동안 수집된 데이터를 로드합니다."""
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / "data" / "logs"

    all_posts = []
    now = datetime.now(KST)
    cutoff = now - timedelta(hours=hours)

    # 최근 2일치 파일 확인 (24시간이 날짜를 넘을 수 있음)
    for i in range(2):
        date = now - timedelta(days=i)
        log_file = log_dir / f"{date.strftime('%Y-%m-%d')}.json"

        if not log_file.exists():
            continue

        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for entry in data:
            collected_at = datetime.fromisoformat(entry["collected_at"])
            if collected_at >= cutoff:
                for post in entry["posts"]:
                    post["collected_at"] = entry["collected_at"]
                    all_posts.append(post)

    # 중복 제거 (같은 ID)
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        if post["id"] not in seen_ids:
            seen_ids.add(post["id"])
            unique_posts.append(post)

    return unique_posts


def analyze_with_ai(posts: list[dict]) -> str:
    """Claude API를 사용하여 트렌드를 분석합니다."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not set"

    client = anthropic.Anthropic(api_key=api_key)

    # 제목 목록 준비
    titles = [f"- {post['title']}" for post in posts[:100]]  # 최대 100개
    titles_text = "\n".join(titles)

    prompt = f"""다음은 뽐뿌 릴레이 게시판에서 최근 수집된 게시물 제목들입니다.
이 데이터를 바탕으로 트렌드 분석을 해주세요.

## 분석 요청사항
1. **인기 키워드**: 자주 언급되는 브랜드/서비스/이벤트 (상위 5개)
2. **트렌드 요약**: 현재 어떤 종류의 이벤트/혜택이 주로 올라오는지
3. **주목할 점**: 특이하거나 눈에 띄는 패턴

## 게시물 제목 ({len(posts)}개)
{titles_text}

간결하게 분석해주세요 (한국어로)."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def save_analysis(analysis: str, post_count: int) -> str:
    """분석 결과를 저장합니다."""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")

    script_dir = Path(__file__).parent.parent
    analysis_dir = script_dir / "data" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    analysis_file = analysis_dir / f"{date_str}.json"

    # 기존 데이터 로드 또는 새 리스트
    if analysis_file.exists():
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    entry = {
        "analyzed_at": now.isoformat(),
        "post_count": post_count,
        "analysis": analysis,
    }
    data.append(entry)

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(analysis_file)


def main():
    print(f"[{datetime.now(KST).isoformat()}] 트렌드 분석 시작...")

    posts = load_recent_data(hours=24)
    print(f"분석 대상 게시물: {len(posts)}개")

    if len(posts) < 5:
        print("분석하기에 데이터가 부족합니다 (최소 5개 필요)")
        return

    analysis = analyze_with_ai(posts)
    print("\n=== 분석 결과 ===")
    print(analysis)

    analysis_file = save_analysis(analysis, len(posts))
    print(f"\n저장 완료: {analysis_file}")


if __name__ == "__main__":
    main()
