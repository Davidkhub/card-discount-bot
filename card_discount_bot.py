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
            viewport={"width": 390, "height": 844},  # 모바일 뷰
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
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
        await page.screenshot(path="screenshots/hmall_before_click.png")
        print("클릭 전 스크린샷 저장")

        # 카드할인 탭 찾기
        card_tab = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('a, button, span, div');
                const results = [];
                all.forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && (text.includes('카드') || text.includes('할인') || text.includes('혜택'))) {
                        results.push({
                            tag: el.tagName,
                            text: text.slice(0, 50),
                            cls: el.className?.toString().slice(0, 60),
                            href: el.href || ''
                        });
                    }
                });
                return results.slice(0, 30);
            }
        """)

        print(f"\n카드/할인/혜택 관련 요소:")
        for el in card_tab:
            print(f"  [{el['tag']}] text={el['text'][:40]} | cls={el['cls'][:40]} | href={el['href'][:60]}")

        # 카드할인 탭 클릭 시도
        print("\n카드할인 탭 클릭 시도...")
        clicked = False
        for keyword in ['카드할인', '카드 할인', '할인&혜택', '할인&amp;혜택', '할인혜택']:
            try:
                el = await page.get_by_text(keyword, exact=False).first.element_handle()
                if el:
                    await el.click()
                    print(f"  클릭 성공: '{keyword}'")
                    clicked = True
                    break
            except Exception as e:
                print(f"  '{keyword}' 실패: {e}")

        if clicked:
            await asyncio.sleep(4)
            await page.screenshot(path="screenshots/hmall_after_click.png")
            print("클릭 후 스크린샷 저장")

            # 현재 URL 확인
            print(f"현재 URL: {page.url}")

            # 페이지 텍스트 추출
            content = await page.evaluate("""
                () => {
                    const body = document.body.innerText;
                    return body.slice(0, 2000);
                }
            """)
            print(f"\n페이지 텍스트 (앞 2000자):\n{content}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
