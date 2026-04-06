#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 구조 디버그")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-font-subpixel-positioning",
                "--font-render-hinting=none",
            ],
        )
        page = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        print("롯데홈쇼핑 접속 중...")
        try:
            await page.goto(
                "https://www.lotteimall.com/",
                wait_until="domcontentloaded",
                timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(6)

        os.makedirs("screenshots", exist_ok=True)

        # 폰트 로딩 무시하고 스크린샷
        try:
            await page.screenshot(
                path="screenshots/lotte_main.png",
                full_page=False,
                timeout=60000,
            )
            print(f"메인 스크린샷 저장 / URL: {page.url}")
        except Exception as e:
            print(f"스크린샷 오류 (무시): {e}")

        # 팝업 닫기
        print("\n팝업 닫기 시도...")
        for selector in [
            ".btn_close", ".pop_close", "[class*='close']",
            "[aria-label='닫기']", "button[class*='Close']",
        ]:
            try:
                els = await page.query_selector_all(selector)
                for el in els:
                    if await el.is_visible():
                        await el.click(force=True)
                        print(f"  닫기: {selector}")
                        await asyncio.sleep(0.5)
            except Exception:
                pass

        # "카드" "청구할인" 관련 텍스트 탐색
        print("\n카드 청구할인 영역 탐색...")
        card_info = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && text.length < 100 && (
                        text.includes('카드 청구할인') ||
                        text.includes('청구할인') ||
                        (text.includes('%') && text.includes('카드'))
                    )) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            results.push({
                                tag: el.tagName,
                                cls: el.className?.toString().slice(0, 60),
                                text: text.slice(0, 80),
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                                href: el.href || ''
                            });
                        }
                    }
                });
                return results.slice(0, 20);
            }
        """)
        print(f"카드 관련 요소 {len(card_info)}개:")
        for el in card_info:
            print(f"  [{el['tag']}] '{el['text']}' x={el['x']} y={el['y']} href={el['href'][:60]}")

        # 전체 텍스트에서 카드 섹션 찾기
        full_text = await page.evaluate("() => document.body.innerText")
        if '청구할인' in full_text:
            idx = full_text.find('청구할인')
            print(f"\n청구할인 주변 텍스트:\n{full_text[max(0,idx-100):idx+300]}")

        # 첫 번째 카드 클릭
        if card_info:
            target = card_info[0]
            print(f"\n첫 번째 카드 클릭: ({target['x']}, {target['y']}) - '{target['text']}'")

            if target['href'] and 'lotteimall' in target['href']:
                await page.goto(target['href'], wait_until="domcontentloaded", timeout=20000)
            else:
                await page.mouse.click(target['x'], target['y'])
            await asyncio.sleep(3)
            print(f"클릭 후 URL: {page.url}")

            try:
                await page.screenshot(path="screenshots/lotte_after_click.png", timeout=60000)
                print("클릭 후 스크린샷 저장")
            except Exception as e:
                print(f"스크린샷 오류: {e}")

            content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
            print(f"\n페이지 텍스트:\n{content}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
