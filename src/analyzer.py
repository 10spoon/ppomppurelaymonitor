#!/usr/bin/env python3
"""AI 기반 트렌드 분석기 - OpenRouter 연동 (다중 모델 비교)"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from openai import OpenAI

KST = timezone(timedelta(hours=9))
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_TITLES = 500

# 사용할 모델
COMPARE_MODELS = [
    "google/gemma-3-27b-it:free",
    "z-ai/glm-4.5-air:free",
    "openai/gpt-oss-120b:free",
]


def load_recent_scrapes(max_entries: int = 1) -> list[dict]:
    """최근 N회 스크래핑 데이터를 로드합니다."""
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / "data" / "logs"

    now = datetime.now(KST)
    entries: list[tuple[datetime, dict]] = []

    for i in range(2):
        date = now - timedelta(days=i)
        log_file = log_dir / f"{date.strftime('%Y-%m-%d')}.json"

        if not log_file.exists():
            continue

        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for entry in data:
            try:
                collected_at = datetime.fromisoformat(entry["collected_at"])
            except Exception:
                continue
            entries.append((collected_at, entry))

    if not entries:
        return []

    entries.sort(key=lambda x: x[0])
    if max_entries < 1:
        max_entries = 1
    entries = entries[-max_entries:]

    all_posts: list[dict] = []
    for _, entry in entries:
        for post in entry.get("posts", []):
            post["collected_at"] = entry.get("collected_at")
            all_posts.append(post)

    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        post_id = post.get("id")
        if post_id and post_id in seen_ids:
            continue
        if post_id:
            seen_ids.add(post_id)
        unique_posts.append(post)

    return unique_posts


def analyze_with_ai(posts: list[dict], model: str, client: OpenAI) -> str | None:
    """지정된 모델로 트렌드를 분석합니다."""
    titles = [f"- {post['title']}" for post in posts[:MAX_TITLES]]
    titles_text = "\n".join(titles)

    prompt = f"""다음은 뽐뿌 릴레이 게시판에서 최근 수집된 게시물 제목들입니다.
이 데이터를 바탕으로 트렌드 분석과 SNS 홍보 문구를 작성해주세요.

## 분석 요청사항
1. 인기 키워드: 자주 언급되는 브랜드/서비스/이벤트 (상위 5개, 간단히)
2. 트렌드 요약: 현재 어떤 종류의 이벤트/혜택이 주로 올라오는지 (2-3문장)

## SNS 홍보 문구
"쌀먹" (ssalmug.com) 관련 X/스레드 게시물을 1개 작성해주세요.

쌀먹 특징 (1-2개만 자연스럽게 녹여서):
- 레퍼럴 링크 복붙하면 AI가 알아서 분류해줌
- 누가 내 링크 누르면 답방하기 편함
- 오래된 링크도 공정하게 노출됨

반드시 지켜야 할 톤앤매너:
- 분석적 말투와 제안형 문장
- "~해보세요", "~있어요" 같은 광고 말투 절대 금지
- 이모지는 1-2개만, 없어도 됨
- 해시태그 2개 이하
- 100자 내외로 짧게
- 마치 본인이 직접 써본 후기처럼

좋은 예시:
- "요즘 케이뱅크 이벤트 쌀먹에서 보고 신청했는데 답방도 바로 됨 ㅋㅋ"
- "추천인 링크 정리하기 귀찮았는데 쌀먹 쓰니까 복붙만 하면 알아서 분류해줌"
- "알뜰폰 갈아타려고 쌀먹 들어갔다가 케뱅 돈나무도 발견 🍀"

나쁜 예시 (이렇게 쓰지 말 것):
- "쌀먹에서 다양한 혜택을 만나보세요!"
- "추천인 프로그램과 함께 즐거운 경험을 해보세요~"

## 게시물 제목 ({len(posts)}개)
{titles_text}

한국어로 작성해주세요."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content
        if content and content.strip():
            return content
        return None

    except Exception as e:
        print(f"  모델 {model} 실패: {e}")
        return None


def analyze_with_multiple_models(posts: list[dict]) -> list[dict]:
    """여러 모델로 분석하여 모든 결과를 반환합니다."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return [{"model": "error", "analysis": "Error: OPENROUTER_API_KEY not set"}]

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )

    results = []

    for model in COMPARE_MODELS:
        print(f"모델 시도: {model}")
        result = analyze_with_ai(posts, model, client)
        if result:
            results.append({
                "model": model,
                "analysis": result,
            })
            print(f"  ✓ 성공")
        else:
            print(f"  ✗ 실패 또는 빈 응답")

    return results


def build_error_result(message: str) -> list[dict]:
    """에러 메시지를 텔레그램으로 보내기 위한 단일 결과 형식."""
    return [{"model": "error", "analysis": message}]


def save_analysis(results: list[dict], post_count: int) -> str:
    """분석 결과를 저장합니다."""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")

    script_dir = Path(__file__).parent.parent
    analysis_dir = script_dir / "data" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    analysis_file = analysis_dir / f"{date_str}.json"

    if analysis_file.exists():
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    entry = {
        "analyzed_at": now.isoformat(),
        "post_count": post_count,
        "results": results,  # 여러 모델 결과
    }
    data.append(entry)

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(analysis_file)


def main():
    print(f"[{datetime.now(KST).isoformat()}] 트렌드 분석 시작...")

    env_value = os.environ.get("ANALYSIS_RECENT_SCRAPES", "").strip()
    try:
        recent_scrapes = int(env_value) if env_value else 6
    except ValueError:
        recent_scrapes = 6
    posts = load_recent_scrapes(recent_scrapes)
    print(f"분석 대상 게시물: {len(posts)}개 (최근 {recent_scrapes}회 스크래핑)")

    if len(posts) < 5:
        print("분석하기에 데이터가 부족합니다 (최소 5개 필요)")
        results = build_error_result(
            f"분석 불가: 데이터 부족 ({len(posts)}개, 최소 5개 필요)"
        )
        analysis_file = save_analysis(results, len(posts))
        print(f"\n저장 완료: {analysis_file}")
        return

    results = analyze_with_multiple_models(posts)
    if not results:
        results = build_error_result("분석 실패: 모든 모델 호출 실패 또는 빈 응답")

    print(f"\n=== 분석 완료: {len(results)}개 모델 성공 ===")
    for r in results:
        print(f"\n--- {r['model']} ---")
        print(r['analysis'][:200] + "..." if len(r['analysis']) > 200 else r['analysis'])

    analysis_file = save_analysis(results, len(posts))
    print(f"\n저장 완료: {analysis_file}")


if __name__ == "__main__":
    main()
