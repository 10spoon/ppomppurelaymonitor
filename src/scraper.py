#!/usr/bin/env python3
"""뽐뿌 릴레이 게시판 스크래퍼"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.ppomppu.co.kr/zboard/zboard.php?id=relay"
KST = timezone(timedelta(hours=9))


def fetch_posts() -> list[dict]:
    """게시판에서 게시물 목록을 가져옵니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.encoding = "euc-kr"  # 뽐뿌는 EUC-KR 인코딩 사용

    soup = BeautifulSoup(response.text, "html.parser")
    posts = []

    # 게시물 행 찾기 (baseList 클래스가 있는 tr - 공지 제외)
    rows = soup.select("tr.baseList")

    for row in rows:
        try:
            # 제목 링크 찾기 (view.php 링크)
            link = row.select_one("a[href*='view.php']")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")

            # 게시물 번호 추출
            post_id = ""
            if "no=" in href:
                post_id = href.split("no=")[-1].split("&")[0]

            # 모든 td 가져오기
            cells = row.select("td")

            # 작성자 (보통 제목 다음 셀)
            author = ""
            for cell in cells:
                if cell.select_one("span.list_name"):
                    author = cell.get_text(strip=True)
                    break

            # 작성 시간 (날짜/시간 형식 찾기)
            timestamp = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if ":" in text and len(text) <= 10:  # 시간 형식 (HH:MM)
                    timestamp = text
                    break
                elif "/" in text and len(text) <= 10:  # 날짜 형식 (MM/DD)
                    timestamp = text
                    break

            if title:  # 제목이 있는 경우만 추가
                posts.append({
                    "id": post_id,
                    "title": title,
                    "author": author,
                    "timestamp": timestamp,
                })
        except Exception:
            continue

    return posts


def load_latest_log_entry() -> dict | None:
    """가장 최근 스크래핑 로그 1건을 반환합니다."""
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / "data" / "logs"

    now = datetime.now(KST)
    latest_entry = None
    latest_time = None

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

            if latest_time is None or collected_at > latest_time:
                latest_time = collected_at
                latest_entry = entry

    return latest_entry


def save_log(posts: list[dict], raw_post_count: int | None = None) -> str:
    """수집한 데이터를 JSON 파일에 저장합니다."""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")

    # 프로젝트 루트 기준 data/logs 디렉토리
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{date_str}.json"

    # 기존 데이터 로드 또는 새 리스트 생성
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    # 새 수집 데이터 추가
    entry = {
        "collected_at": now.isoformat(),
        "post_count": len(posts),
        "posts": posts,
    }
    if raw_post_count is not None:
        entry["raw_post_count"] = raw_post_count
    data.append(entry)

    # 저장
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(log_file)


def main():
    print(f"[{datetime.now(KST).isoformat()}] 스크래핑 시작...")

    raw_posts = fetch_posts()
    latest_entry = load_latest_log_entry()

    if latest_entry:
        seen_ids = {
            post.get("id")
            for post in latest_entry.get("posts", [])
            if post.get("id")
        }
        posts = [
            post for post in raw_posts
            if not post.get("id") or post.get("id") not in seen_ids
        ]
    else:
        posts = raw_posts

    print(f"수집된 게시물: {len(raw_posts)}개 (신규 {len(posts)}개)")

    log_file = save_log(posts, raw_post_count=len(raw_posts))
    print(f"저장 완료: {log_file}")

    if posts:
        # 신규 5개 제목 출력
        print("\n최근 게시물:")
        for post in posts[:5]:
            print(f"  - {post['title']}")
    else:
        print("신규 게시물이 없습니다.")


if __name__ == "__main__":
    main()
