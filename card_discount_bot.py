#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 폰트 차단 후 캡처")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-web-security",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        # 폰트/이미지 요청 차단
        async def block_fonts(route):
            if route.request.resource_type in ["font"]:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_fonts)

        page = await context.new_page()

        print("롯데홈쇼핑 접속 중...")
        try:
            await page.goto(
                "https://www.lotteimall.com/",
                wait_until="domcontentloaded", timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(6)

        os.makedirs("screenshots", exist_ok=True)

        # 팝업 닫기
        for selector in [".btn_close", ".pop_close", "[class*='close']", "[aria-label='닫기']"]:
            try:
                els = await page.query_selector_all(selector)
                for el in els:
                    if await el.is_visible():
                        await el.click(force=True)
                        await asyncio.sleep(0.3)
            except Exception:
                pass

        # 카드 청구할인 섹션 요소 스크린샷
        print("\n카드 청구할인 섹션 캡처...")
        section = await page.query_selector("[class*='f_bnr_card_prom']")
        if section:
            # 요소 위치로 스크롤
            await section.scroll_into_view_if_needed()
            await asyncio.sleep(2)

            path = "screenshots/lotte_card_section.png"
            await section.screenshot(path=path)
            print(f"  섹션 스크린샷 저장: {path}")

            text = await section.inner_text()
            print(f"  섹션 텍스트:\n{text}")

            # 오늘 카드 클릭 요소 찾기
            cards = await page.evaluate("""
                () => {
                    const section = document.querySelector("[class*='f_bnr_card_prom']");
                    if (!section) return [];
                    const results = [];
                    section.querySelectorAll('*').forEach(el => {
                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                        if (text && text.includes('청구할인') && text.includes('%') && text.length < 30) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 30 && rect.height > 30) {
                                results.push({
                                    tag: el.tagName,
                                    text,
                                    x: Math.round(rect.left + rect.width / 2),
                                    y: Math.round(rect.top + rect.height / 2),
                                    cls: el.className?.toString().slice(0, 60),
                                    cursor: window.getComputedStyle(el).cursor,
                                    href: el.href || ''
                                });
                            }
                        }
                    });
                    return results;
                }
            """)
            print(f"\n섹션 내 카드 요소 {len(cards)}개:")
            for c in cards:
                print(f"  [{c['tag']}] '{c['text']}' x={c['x']} y={c['y']} cursor={c['cursor']} href={c['href'][:80]}")

            # 첫 번째 카드 클릭
            if cards:
                target = cards[0]
                print(f"\n첫 번째 카드 클릭: ({target['x']}, {target['y']})")
                await page.mouse.click(target['x'], target['y'])
                await asyncio.sleep(3)
                print(f"클릭 후 URL: {page.url}")

                # 클릭 후 화면 캡처
                await page.screenshot(path="screenshots/lotte_after_click.png")
                print("클릭 후 스크린샷 저장")

                content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
                print(f"\n클릭 후 텍스트:\n{content}")
        else:
            print("  섹션 못 찾음")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
