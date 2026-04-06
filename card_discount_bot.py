#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 카드탭 구조 디버그")

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

        print("Hmall 접속 중...")
        try:
            await page.goto(
                "https://www.hmall.com/md/dpl/index",
                wait_until="domcontentloaded",
                timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
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

        await page.screenshot(path="screenshots/hmall_01_benefit.png")

        # "오늘" 텍스트 근처 전체 HTML 구조 출력
        print("\n오늘 섹션 HTML 구조:")
        html_structure = await page.evaluate("""
            () => {
                // '오늘' 텍스트를 포함한 부모 컨테이너 찾기
                let todayEl = null;
                document.querySelectorAll('*').forEach(el => {
                    if (el.childNodes.length === 1 &&
                        el.innerText?.trim() === '오늘') {
                        todayEl = el;
                    }
                });
                if (!todayEl) return 'oday 요소 못 찾음';

                // 부모 컨테이너 5단계 위까지 올라가기
                let container = todayEl;
                for (let i = 0; i < 5; i++) {
                    if (container.parentElement) container = container.parentElement;
                }
                return container.outerHTML.slice(0, 3000);
            }
        """)
        print(html_structure)

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
