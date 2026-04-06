#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 카드청구할인 상세 페이지 디버그")

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

        # 폰트 차단
        async def block_fonts(route):
            if route.request.resource_type == "font":
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_fonts)

        page = await context.new_page()

        # 메인에서 카드 청구할인 링크 URL 먼저 찾기
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

        # f_bnr_card_prom 섹션에서 href 찾기
        print("\n카드 청구할인 섹션 링크 탐색...")
        links = await page.evaluate("""
            () => {
                const section = document.querySelector("[class*='f_bnr_card_prom']");
                if (!section) return [];
                const results = [];
                section.querySelectorAll('a').forEach(el => {
                    results.push({
                        text: el.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 50),
                        href: el.href,
                        cls: el.className?.toString().slice(0, 40)
                    });
                });
                return results;
            }
        """)
        print(f"섹션 내 링크 {len(links)}개:")
        for l in links:
            print(f"  '{l['text']}' -> {l['href']}")

        # 새 페이지 감지하면서 클릭
        print("\n카드 클릭 시 새 페이지/URL 감지...")
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

        # 첫 번째 카드 클릭 - 새 탭 감지
        if section_cards:
            target = section_cards[0]
            print(f"\n첫 번째 카드 클릭 (새 탭 감지): '{target['text']}'")
            try:
                async with context.expect_page(timeout=5000) as new_page_info:
                    await page.mouse.click(target['x'], target['y'])
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)
                print(f"  새 탭 URL: {new_page.url}")

                # 탭 목록 확인
                tabs = await new_page.evaluate("""
                    () => {
                        const results = [];
                        document.querySelectorAll('a, button, li').forEach(el => {
                            const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                            if (text && (text.includes('롯데') || text.includes('KB') || text.includes('현대') || text.includes('카드'))
                                && text.length < 20) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 30 && rect.height > 20) {
                                    results.push({
                                        tag: el.tagName, text,
                                        x: Math.round(rect.left + rect.width / 2),
                                        y: Math.round(rect.top + rect.height / 2),
                                        cls: el.className?.toString().slice(0, 50)
                                    });
                                }
                            }
                        });
                        return results;
                    }
                """)
                print(f"\n  탭 목록 {len(tabs)}개:")
                for t in tabs:
                    print(f"    [{t['tag']}] '{t['text']}' x={t['x']} y={t['y']}")

                # 스크린샷 시도
                os.makedirs("screenshots", exist_ok=True)
                try:
                    await new_page.screenshot(path="screenshots/lotte_detail.png", timeout=10000)
                    print("  스크린샷 저장 성공!")
                except Exception as e:
                    print(f"  스크린샷 실패: {e}")

                content = await new_page.evaluate("() => document.body.innerText.slice(0, 500)")
                print(f"\n  페이지 텍스트:\n{content}")

            except Exception as e:
                print(f"  새 탭 없음: {e}")
                # URL 변화 확인
                before = page.url
                await page.mouse.click(target['x'], target['y'])
                await asyncio.sleep(3)
                after = page.url
                print(f"  클릭 전: {before}")
                print(f"  클릭 후: {after}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
