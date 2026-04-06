#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("CJ온스타일 HTML 구조 디버그 시작")

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

        print("페이지 접속 중...")
        await page.goto(
            "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005",
            wait_until="networkidle",
            timeout=40000,
        )
        await asyncio.sleep(5)

        # 전체 스크린샷 저장
        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/cj_fullpage.png", full_page=True)
        print("전체 스크린샷 저장 완료: screenshots/cj_fullpage.png")

        # 카드 관련 요소 클래스명 출력
        classes = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                const cardClasses = new Set();
                all.forEach(el => {
                    el.classList.forEach(cls => {
                        if (/card|benefit|discount|Card|Benefit|Discount/i.test(cls)) {
                            cardClasses.add(cls + ' (tag: ' + el.tagName + ')');
                        }
                    });
                });
                return [...cardClasses];
            }
        """)

        print(f"\n카드/혜택 관련 클래스명 {len(classes)}개 발견:")
        for c in classes:
            print(f"  {c}")

        # 페이지 높이 확인
        height = await page.evaluate("document.body.scrollHeight")
        print(f"\n페이지 전체 높이: {height}px")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
