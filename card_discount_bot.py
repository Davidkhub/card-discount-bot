#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 카드청구할인 영역 캡처 디버그")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-web-security",
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

        # "카드 청구할인" 텍스트 요소 찾기 → 해당 영역 스크롤 후 캡처
        print("\n카드 청구할인 영역 찾기...")
        section_info = await page.evaluate("""
            () => {
                let target = null;
                document.querySelectorAll('*').forEach(el => {
                    if (el.childNodes.length <= 3 &&
                        el.innerText?.trim() === '카드 청구할인') {
                        target = el;
                    }
                });
                if (!target) return null;

                // 부모 컨테이너 찾기 (카드들 포함)
                let container = target;
                for (let i = 0; i < 6; i++) {
                    if (container.parentElement) container = container.parentElement;
                    const h = container.getBoundingClientRect().height;
                    if (h > 150) break;
                }
                const rect = container.getBoundingClientRect();
                return {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top + window.scrollY),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    cls: container.className?.toString().slice(0, 60),
                    tag: container.tagName
                };
            }
        """)
        print(f"카드 청구할인 섹션: {section_info}")

        if section_info:
            # 해당 위치로 스크롤
            scroll_y = max(0, section_info['y'] - 100)
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(2)

            # 스크린샷 (뷰포트 기준)
            await page.screenshot(
                path="screenshots/lotte_card_section.png",
                timeout=60000,
                clip={
                    "x": 0,
                    "y": 0,
                    "width": 1280,
                    "height": 900,
                }
            )
            print("카드 청구할인 섹션 스크린샷 저장!")

            # 오늘 카드 클릭 요소 찾기
            cards = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('*').forEach(el => {
                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                        if (text && text.includes('청구할인') && text.includes('%') && text.length < 30) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 30 && rect.height > 30 && rect.top > 0) {
                                results.push({
                                    tag: el.tagName,
                                    text,
                                    x: Math.round(rect.left + rect.width / 2),
                                    y: Math.round(rect.top + rect.height / 2),
                                    cls: el.className?.toString().slice(0, 60),
                                    href: el.href || el.onclick?.toString().slice(0, 80) || ''
                                });
                            }
                        }
                    });
                    return results;
                }
            """)
            print(f"\n오늘 카드 요소 {len(cards)}개:")
            for c in cards:
                print(f"  [{c['tag']}] '{c['text']}' x={c['x']} y={c['y']} cls={c['cls'][:40]}")

            # 첫 번째 카드 클릭
            if cards:
                target = cards[0]
                print(f"\n첫 번째 카드 클릭: ({target['x']}, {target['y']})")
                await page.mouse.click(target['x'], target['y'])
                await asyncio.sleep(3)
                print(f"클릭 후 URL: {page.url}")

                await page.screenshot(
                    path="screenshots/lotte_after_click.png",
                    timeout=60000,
                )
                print("클릭 후 스크린샷 저장")

                content = await page.evaluate("() => document.body.innerText.slice(0, 800)")
                print(f"\n클릭 후 텍스트:\n{content}")
        else:
            print("카드 청구할인 섹션 못 찾음")
            full_text = await page.evaluate("() => document.body.innerText")
            idx = full_text.find('청구할인')
            if idx >= 0:
                print(f"청구할인 주변:\n{full_text[max(0,idx-50):idx+300]}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
