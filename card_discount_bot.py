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

        # 팝업 닫기
        print("팝업 닫기...")
        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
                print("  팝업 닫기 성공")
        except Exception as e:
            print(f"  팝업 닫기 실패: {e}")

        # JS로 팝업 강제 제거
        await page.evaluate("() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }")
        await asyncio.sleep(1)

        # 혜택 탭 클릭 (data-maindispseq="7" 속성으로 정확히 찾기)
        print("\n혜택 탭 클릭 시도...")
        clicked = False
        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                text = await el.inner_text()
                print(f"  요소 발견: '{text}'")
                await el.click(force=True)
                print("  클릭 성공!")
                clicked = True
                await asyncio.sleep(4)
                print(f"  클릭 후 URL: {page.url}")
                await page.screenshot(path="screenshots/hmall_after_tab.png")
        except Exception as e:
            print(f"  data-maindispseq 클릭 실패: {e}")

        if not clicked:
            # 직접 혜택 앱 URL로 이동
            print("\n직접 혜택 URL로 이동...")
            try:
                await page.goto(
                    "https://www.hmall.com/md/app/main/index?mainDispSeq=7&mblMainTmplGbcd=07",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await asyncio.sleep(4)
                print(f"  URL: {page.url}")
                await page.screenshot(path="screenshots/hmall_benefit.png")
                clicked = True
            except Exception as e:
                print(f"  실패: {e}")

        if clicked:
            # 페이지에서 카드할인 탭 찾기
            print("\n카드할인 탭 요소 탐색...")
            tabs = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('a, button, li, span').forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && text.includes('카드')) {
                            results.push({
                                tag: el.tagName,
                                text: text.slice(0, 50),
                                cls: el.className?.toString().slice(0, 60),
                                href: el.href || ''
                            });
                        }
                    });
                    return results.slice(0, 20);
                }
            """)
            for t in tabs:
                print(f"  [{t['tag']}] text={t['text']} | cls={t['cls'][:40]} | href={t['href'][:80]}")

            # 페이지 텍스트
            content = await page.evaluate("() => document.body.innerText.slice(0, 1000)")
            print(f"\n페이지 텍스트:\n{content}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
