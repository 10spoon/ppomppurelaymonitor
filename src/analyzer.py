#!/usr/bin/env python3
"""AI 기반 트렌드 분석기 - OpenRouter 연동"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from openai import OpenAI

KST = timezone(timedelta(hours=9))
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 무료 모델 우선순위 (fallback 순서)
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-3-1b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen3-4b:free",
]


def get_available_free_models(api_key: str) -> list[str]:
    """OpenRouter API에서 사용 가능한 무료 모델 목록을 가져옵니다."""
    try:
        response = requests.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        models = response.json().get("data", [])

        # 무료 모델 필터링 (pricing이 0이거나 :free 접미사)
        free_models = []
        for model in models:
            model_id = model.get("id", "")
            pricing = model.get("pricing", {})

            is_free = (
                ":free" in model_id
                or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
            )

            if is_free:
                free_models.append(model_id)

        return free_models
    except Exception as e:
        print(f"모델 목록 조회 실패: {e}")
        return []


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


def analyze_with_ai(posts: list[dict], model: str, client: OpenAI) -> str | None:
    """지정된 모델로 트렌드를 분석합니다."""
    # 제목 목록 준비
    titles = [f"- {post['title']}" for post in posts[:100]]  # 최대 100개
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
- 친구한테 카톡하듯 편하게 쓰기
- "~해보세요", "~있어요" 같은 광고 말투 절대 금지
- "~하더라", "~였음", "~ㅋㅋ", "~인듯" 같은 자연스러운 말투 사용
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
        # 빈 응답 체크
        if content and content.strip():
            return content
        return None

    except Exception as e:
        print(f"  모델 {model} 실패: {e}")
        return None


def analyze_with_fallback(posts: list[dict]) -> tuple[str, str]:
    """여러 무료 모델을 시도하여 분석합니다. (model, result) 반환"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "", "Error: OPENROUTER_API_KEY not set"

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )

    # 사용 가능한 무료 모델 조회
    available = get_available_free_models(api_key)
    print(f"사용 가능한 무료 모델: {len(available)}개")

    # 우선순위 모델 + 동적으로 발견된 모델
    models_to_try = []
    for model in FREE_MODELS:
        if model in available or not available:  # available이 비면 그냥 시도
            models_to_try.append(model)

    # 추가로 발견된 무료 모델 (우선순위에 없는 것들)
    for model in available:
        if model not in models_to_try:
            models_to_try.append(model)

    # Fallback 시도
    for model in models_to_try[:5]:  # 최대 5개 모델 시도
        print(f"모델 시도: {model}")
        result = analyze_with_ai(posts, model, client)
        if result:
            return model, result

    return "", "Error: 모든 모델에서 분석 실패"


def save_analysis(analysis: str, post_count: int, model: str) -> str:
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
        "model": model,
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

    model, analysis = analyze_with_fallback(posts)

    print("\n=== 분석 결과 ===")
    if model:
        print(f"사용 모델: {model}")
    print(analysis)

    analysis_file = save_analysis(analysis, len(posts), model)
    print(f"\n저장 완료: {analysis_file}")


if __name__ == "__main__":
    main()
