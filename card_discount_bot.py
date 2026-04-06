#!/usr/bin/env python3
import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 스크롤 후 클릭 디버그")

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

        # 카드 섹션으로 스크롤 후 클릭
        section = await page.query_selector("[class*='f_bnr_card_prom']")
        if section:
            await section.scroll_into_view_if_needed()
            await asyncio.sleep(2)

            # 스크롤 후 좌표 재계산
            card_link = await page.query_selector("[class*='f_bnr_card_prom'] a")
            if card_link:
                box = await card_link.bounding_box()
                print(f"카드 링크 위치: {box}")

                # 새 탭 감지하면서 클릭
                print("\n새 탭 감지하면서 클릭...")
                try:
                    async with context.expect_page(timeout=8000) as new_page_info:
                        await card_link.click()
                    new_page = await new_page_info.value
                    await new_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(4)
                    print(f"  새 탭 URL: {new_page.url}")

                    # 탭 목록 수집
                    tabs = await new_page.evaluate("""
                        () => {
                            const results = [];
                            document.querySelectorAll('a, button, li').forEach(el => {
                                const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                                if (text && text.length < 20 && (
                                    text.includes('롯데') || text.includes('KB') ||
                                    text.includes('현대') || text.includes('카드')
                                )) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width > 30 && rect.height > 10) {
                                        results.push({
                                            tag: el.tagName, text,
                                            x: Math.round(rect.left + rect.width/2),
                                            y: Math.round(rect.top + rect.height/2),
                                            cls: el.className?.toString().slice(0, 50)
                                        });
                                    }
                                }
                            });
                            return results;
                        }
                    """)
                    print(f"  탭 목록 {len(tabs)}개:")
                    for t in tabs:
                        print(f"    [{t['tag']}] '{t['text']}' x={t['x']} y={t['y']}")

                    content = await new_page.evaluate("() => document.body.innerText.slice(0, 500)")
                    print(f"\n  페이지 텍스트:\n{content}")

                except Exception as e:
                    print(f"  새 탭 없음: {e}")
                    # JS로 직접 클릭 이벤트 실행
                    print("\nJS로 링크 클릭...")
                    result = await page.evaluate("""
                        () => {
                            const section = document.querySelector("[class*='f_bnr_card_prom']");
                            const link = section?.querySelector('a');
                            if (link) {
                                link.click();
                                return { found: true, href: link.href, onclick: link.getAttribute('onclick') };
                            }
                            return { found: false };
                        }
                    """)
                    print(f"  JS 클릭 결과: {result}")
                    await asyncio.sleep(3)
                    print(f"  클릭 후 URL: {page.url}")

                    # DOM 변화 확인
                    new_text = await page.evaluate("() => document.body.innerText")
                    if "현대카드" in new_text:
                        idx = new_text.find("현대카드")
                        print(f"  현대카드 발견:\n{new_text[max(0,idx-100):idx+300]}")
                    else:
                        print("  현대카드 여전히 없음")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
