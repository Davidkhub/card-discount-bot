#!/usr/bin/env python3
import asyncio
import os
from playwright.async_api import async_playwright

MOB_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

async def main():
    print("CJ온스타일 카드/결제혜택 탭 디버그")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(
            viewport={"width": 390, "height": 844},
            user_agent=MOB_UA,
        )

        print("접속 중...")
        await page.goto(
            "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00009",
            wait_until="networkidle", timeout=40000,
        )
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/cj_before.png")
        print("초기 스크린샷 저장")

        # "카드/결제혜택" 탭 찾기
        print("\n탭 목록 탐색...")
        tabs = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('a, button, span, div, li').forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && (
                        text.includes('카드/결제') ||
                        text.includes('카드결제') ||
                        text.includes('카드/결제혜택') ||
                        text === '카드혜택' ||
                        text === '결제혜택'
                    )) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            tag: el.tagName,
                            text,
                            cls: el.className?.toString().slice(0, 60),
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            href: el.href || ''
                        });
                    }
                });
                return results;
            }
        """)
        print(f"카드/결제혜택 탭 요소 {len(tabs)}개:")
        for t in tabs:
            print(f"  [{t['tag']}] '{t['text']}' x={t['x']} y={t['y']} cls={t['cls'][:40]}")

        # 탭 클릭 시도
        if tabs:
            target = tabs[0]
            print(f"\n탭 클릭: '{target['text']}' ({target['x']}, {target['y']})")
            await page.mouse.click(target['x'], target['y'])
            await asyncio.sleep(3)
            await page.screenshot(path="screenshots/cj_after_tab.png", full_page=True)
            print("탭 클릭 후 스크린샷 저장")
            print(f"URL: {page.url}")

            # 클릭 후 카드 영역 확인
            content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
            print(f"\n페이지 텍스트:\n{content}")

        # 스크롤 내리면서 탭 다시 찾기
        print("\n스크롤하면서 탭 탐색...")
        for scroll_pos in [300, 600, 900, 1200]:
            await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
            await asyncio.sleep(1)
            tabs2 = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('a, button, span, div, li').forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && (text.includes('카드/결제') || text.includes('카드결제혜택'))) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.top > 0 && rect.top < 844) {
                                results.push({
                                    tag: el.tagName, text,
                                    x: Math.round(rect.left + rect.width/2),
                                    y: Math.round(rect.top + rect.height/2)
                                });
                            }
                        }
                    });
                    return results;
                }
            """)
            if tabs2:
                print(f"  스크롤 {scroll_pos}px 에서 발견: {[t['text'] for t in tabs2]}")
                target = tabs2[0]
                await page.mouse.click(target['x'], target['y'])
                await asyncio.sleep(3)
                await page.screenshot(path=f"screenshots/cj_scroll_{scroll_pos}.png")
                print(f"  클릭 후 스크린샷 저장")
                break

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
