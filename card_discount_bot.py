#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 페이지 구조 디버그 시작")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        print("Hmall 접속 중...")
        await page.goto(
            "https://www.hmall.com/md/dpl/index",
            wait_until="networkidle",
            timeout=40000,
        )
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/hmall_debug.png", full_page=False)
        print("스크린샷 저장 완료")

        # 오늘 날짜 관련 요소 찾기
        today = datetime.now()
        today_str_candidates = [
            f"{today.month}.{today.day}",
            f"{today.month}/{today.day}",
            f"{today.month}월 {today.day}일",
            f"0{today.month}.0{today.day}" if today.month < 10 and today.day < 10 else "",
        ]
        print(f"\n오늘 날짜 후보: {today_str_candidates}")

        # 클릭 가능한 카드/링크 요소 출력
        elements = await page.evaluate("""
            () => {
                const results = [];
                const candidates = document.querySelectorAll('a, button, li, div[class*="card"], div[class*="item"]');
                candidates.forEach(el => {
                    const text = el.innerText?.trim().replace(/\\n/g, ' ').slice(0, 80);
                    const cls = el.className?.toString().slice(0, 60);
                    const href = el.href || '';
                    if (text && text.length > 2 && text.length < 100) {
                        results.push({ tag: el.tagName, cls, text, href });
                    }
                });
                return results.slice(0, 60);
            }
        """)

        print(f"\n요소 목록 ({len(elements)}개):")
        for el in elements:
            print(f"  [{el['tag']}] cls={el['cls'][:40]} | text={el['text'][:50]} | href={el['href'][:60]}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
