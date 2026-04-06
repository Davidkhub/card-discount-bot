#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 카드할인 디버그 시작")

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
            print(f"goto 예외 무시: {e}")

        await asyncio.sleep(5)
        os.makedirs("screenshots", exist_ok=True)

        # 팝업 닫기 시도
        print("팝업 닫기 시도...")
        popup_closed = False
        for popup_selector in [
            "[aria-label='메인 배너 팝업'] button",
            "[role='dialog'] button",
            "button[class*='close']",
            "button[class*='Close']",
            "[aria-label='닫기']",
            "button[class*='dismiss']",
        ]:
            try:
                el = await page.query_selector(popup_selector)
                if el:
                    await el.click(force=True)
                    print(f"  팝업 닫기 성공: {popup_selector}")
                    popup_closed = True
                    await asyncio.sleep(1)
                    break
            except Exception as e:
                print(f"  {popup_selector} 실패: {e}")

        # 팝업 닫기 버튼 못찾으면 Escape 키로 닫기
        if not popup_closed:
            print("  Escape 키로 팝업 닫기 시도...")
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

        # 팝업 강제 제거 (JS로)
        print("  JS로 팝업 강제 제거...")
        await page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('[role="dialog"], #modal-root > *');
                dialogs.forEach(el => el.remove());
            }
        """)
        await asyncio.sleep(1)

        await page.screenshot(path="screenshots/hmall_no_popup.png")
        print("팝업 제거 후 스크린샷 저장")

        # 카드할인 탭 클릭
        print("\n카드할인 탭 클릭 시도...")
        clicked = False
        for keyword in ['카드할인', '혜택', '카드']:
            try:
                locator = page.get_by_text(keyword, exact=False).first
                count = await locator.count()
                if count > 0:
                    await locator.click(force=True, timeout=5000)
                    print(f"  클릭 성공: '{keyword}'")
                    clicked = True
                    await asyncio.sleep(4)
                    print(f"  클릭 후 URL: {page.url}")
                    await page.screenshot(path="screenshots/hmall_after_click.png")
                    print("  클릭 후 스크린샷 저장")

                    content = await page.evaluate("() => document.body.innerText.slice(0, 2000)")
                    print(f"\n페이지 텍스트:\n{content}")
                    break
            except Exception as e:
                print(f"  '{keyword}' 실패: {e}")

        if not clicked:
            # 직접 URL로 접근 시도
            print("\n직접 URL 접근 시도...")
            try:
                await page.goto(
                    "https://www.hmall.com/md/app/main/index?mainDispSeq=7&mblMainTmplGbcd=07",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await asyncio.sleep(4)
                print(f"  URL: {page.url}")
                await page.screenshot(path="screenshots/hmall_direct.png")
                content = await page.evaluate("() => document.body.innerText.slice(0, 2000)")
                print(f"\n페이지 텍스트:\n{content}")
            except Exception as e:
                print(f"  직접 URL 접근 실패: {e}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
