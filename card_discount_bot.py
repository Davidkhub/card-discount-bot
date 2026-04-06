#!/usr/bin/env python3
import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 클릭 후 레이어 텍스트 수집")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        async def block_fonts(route):
            if route.request.resource_type == "font":
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_fonts)

        page = await context.new_page()

        print("메인 페이지 접속 중...")
        try:
            await page.goto("https://www.lotteimall.com/", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(6)

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

        # 카드 섹션 클릭
        section_cards = await page.evaluate("""
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
                                tag: el.tagName, text,
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                            });
                        }
                    }
                });
                return results;
            }
        """)

        if not section_cards:
            print("카드 섹션 못 찾음")
            await browser.close()
            return

        target = section_cards[0]
        print(f"\n카드 클릭: '{target['text']}'")
        await page.mouse.click(target['x'], target['y'])
        await asyncio.sleep(3)
        print(f"클릭 후 URL: {page.url}")

        # 클릭 후 DOM 변화 확인 - 새로 생긴 요소 찾기
        print("\n클릭 후 DOM 탐색...")

        # 전체 페이지 텍스트에서 카드 정보 찾기
        full_text = await page.evaluate("() => document.body.innerText")
        if "현대카드" in full_text:
            idx = full_text.find("현대카드")
            print(f"현대카드 발견! 주변 텍스트:\n{full_text[max(0,idx-200):idx+300]}")
        else:
            print("현대카드 텍스트 없음")

        # 새로 추가된 레이어/모달 찾기
        new_elements = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && (text.includes('현대카드') || text.includes('롯데카드')) && text.length < 500) {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (rect.width > 100 && style.display !== 'none' && style.visibility !== 'hidden') {
                            results.push({
                                tag: el.tagName,
                                cls: el.className?.toString().slice(0, 80),
                                text: text.slice(0, 200),
                                display: style.display,
                                position: style.position,
                                zIndex: style.zIndex
                            });
                        }
                    }
                });
                return results.slice(0, 10);
            }
        """)
        print(f"\n현대카드/롯데카드 포함 요소 {len(new_elements)}개:")
        for el in new_elements:
            print(f"  [{el['tag']}] cls={el['cls'][:50]}")
            print(f"    text='{el['text'][:100]}'")
            print(f"    display={el['display']} position={el['position']} zIndex={el['zIndex']}")

        # 탭 구조 찾기
        tabs = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && (text === '롯데카드' || text === 'KB국민' || text === '현대카드') ) {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (rect.width > 0 && style.display !== 'none') {
                            results.push({
                                tag: el.tagName,
                                cls: el.className?.toString().slice(0, 60),
                                text,
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                            });
                        }
                    }
                });
                return results;
            }
        """)
        print(f"\n탭 요소 {len(tabs)}개:")
        for t in tabs:
            print(f"  [{t['tag']}] '{t['text']}' x={t['x']} y={t['y']} cls={t['cls'][:40]}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
