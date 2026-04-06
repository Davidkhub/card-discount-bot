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
                wait_until="domcontentloaded",  # networkidle 대신 완화
                timeout=40000,
            )
        except Exception as e:
            print(f"goto 예외 (무시하고 계속): {e}")

        await asyncio.sleep(6)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/hmall_main.png")
        print(f"현재 URL: {page.url}")
        print("메인 스크린샷 저장")

        # 카드할인 관련 링크 찾기
        links = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('a').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    const href = el.href || '';
                    if (text && (
                        text.includes('카드') ||
                        text.includes('할인') ||
                        text.includes('혜택') ||
                        href.includes('card') ||
                        href.includes('dc') ||
                        href.includes('dpl')
                    )) {
                        results.push({ text: text.slice(0, 60), href: href.slice(0, 100) });
                    }
                });
                return results.slice(0, 30);
            }
        """)

        print(f"\n카드/할인 관련 링크:")
        for l in links:
            print(f"  text={l['text'][:50]} | href={l['href']}")

        # 카드할인 탭 클릭 시도
        print("\n클릭 시도...")
        for keyword in ['카드할인', '할인&혜택', '혜택', '카드']:
            try:
                locator = page.get_by_text(keyword, exact=False).first
                count = await locator.count()
                if count > 0:
                    await locator.click(timeout=5000)
                    print(f"  클릭 성공: '{keyword}'")
                    await asyncio.sleep(4)
                    print(f"  클릭 후 URL: {page.url}")
                    await page.screenshot(path="screenshots/hmall_after_click.png")
                    print("  클릭 후 스크린샷 저장")

                    content = await page.evaluate("() => document.body.innerText.slice(0, 1500)")
                    print(f"\n  페이지 텍스트:\n{content}")
                    break
            except Exception as e:
                print(f"  '{keyword}' 실패: {e}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
