#!/usr/bin/env python3
import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    print("CJ온스타일 혜택탭 구조 디버그")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            ),
        )

        print("접속 중...")
        await page.goto(
            "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00009",
            wait_until="networkidle", timeout=40000,
        )
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/cj_benefit_full.png", full_page=True)
        print("전체 스크린샷 저장")

        # 카드/결제혜택 관련 클래스명 찾기
        classes = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                const found = new Set();
                all.forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && (
                        text.includes('카드') ||
                        text.includes('결제혜택') ||
                        text.includes('카드/결제')
                    ) && text.length < 30) {
                        el.classList.forEach(cls => found.add(cls + ' (tag:' + el.tagName + ')'));
                        // 부모 클래스도 수집
                        let parent = el.parentElement;
                        for (let i = 0; i < 5; i++) {
                            if (!parent) break;
                            parent.classList.forEach(cls => found.add(cls + ' (tag:' + parent.tagName + ')'));
                            parent = parent.parentElement;
                        }
                    }
                });
                return [...found];
            }
        """)
        print(f"\n카드/결제혜택 관련 클래스 {len(classes)}개:")
        for c in classes:
            print(f"  {c}")

        # 페이지 전체 텍스트 (하단 부분)
        full_text = await page.evaluate("() => document.body.innerText")
        if '카드' in full_text:
            idx = full_text.rfind('카드')
            print(f"\n카드 관련 텍스트 (하단):\n{full_text[max(0,idx-200):idx+500]}")

        # 페이지 높이
        height = await page.evaluate("() => document.body.scrollHeight")
        print(f"\n페이지 전체 높이: {height}px")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
