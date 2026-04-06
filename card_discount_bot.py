#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall HTML 전체 덤프")

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

        try:
            await page.goto("https://www.hmall.com/md/dpl/index", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"goto 예외 무시: {e}")
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)

        # 팝업 닫기
        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
        except Exception:
            pass
        await page.evaluate("() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }")
        await asyncio.sleep(1)

        # 혜택 탭 클릭
        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                await el.click(force=True)
                await asyncio.sleep(4)
                print("혜택 탭 클릭 성공")
        except Exception as e:
            print(f"혜택 탭 클릭 실패: {e}")

        # 전체 텍스트 출력
        full_text = await page.evaluate("() => document.body.innerText")
        print("\n=== 전체 텍스트 ===")
        print(full_text[:5000])

        # 전체 링크 중 카드할인 상세 URL 패턴 찾기
        print("\n=== 모든 링크 ===")
        links = await page.evaluate("""
            () => [...document.querySelectorAll('a')].map(a => ({
                text: a.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 40),
                href: a.href
            })).filter(l => l.href && !l.href.endsWith('#') && l.href.includes('hmall'))
        """)
        for l in links:
            print(f"  '{l['text']}' -> {l['href']}")

        await browser.close()
        print("\n완료")

if __name__ == "__main__":
    asyncio.run(main())
