#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 텍스트 수집 + 클릭 후 URL 확인")

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

        # 폰트만 차단
        async def block_fonts(route):
            if route.request.resource_type == "font":
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

        # 카드 섹션 텍스트 수집
        print("\n카드 청구할인 텍스트 수집...")
        section = await page.query_selector("[class*='f_bnr_card_prom']")
        if section:
            text = await section.inner_text()
            print(f"섹션 텍스트:\n{text}")

            # 오늘 카드 클릭 요소 좌표 수집
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
                                    href: el.href || ''
                                });
                            }
                        }
                    });
                    return results;
                }
            """)
            print(f"\n카드 요소 {len(cards)}개:")
            for c in cards:
                print(f"  [{c['tag']}] '{c['text']}' x={c['x']} y={c['y']} href={c['href'][:80]}")

            # 각 카드 클릭 후 URL 수집
            print("\n각 카드 URL 수집...")
            card_urls = []

            # 오늘 카드만 (4.7 이전 카드들)
            # 텍스트에서 오늘/내일 구분
            import re
            today_count = 0
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            found_today = False
            for line in lines:
                if '오늘' in line:
                    found_today = True
                    continue
                if found_today and re.match(r'\d+\.\d+', line):
                    break
                if found_today and '청구할인' in line:
                    today_count += 1

            print(f"오늘 카드 수: {today_count}")
            today_cards = cards[:today_count] if today_count > 0 else cards[:2]

            for i, card in enumerate(today_cards):
                print(f"\n  [{i+1}] 클릭: '{card['text']}'")
                await page.mouse.click(card['x'], card['y'])
                await asyncio.sleep(3)
                url = page.url
                print(f"  클릭 후 URL: {url}")

                if url != "https://www.lotteimall.com/main/viewMain.lotte#disp_no=5223317&isWebp=Y":
                    card_urls.append({"name": card['text'], "url": url})
                else:
                    # URL 안 바뀌면 href 사용
                    if card['href'] and 'lotteimall' in card['href']:
                        card_urls.append({"name": card['text'], "url": card['href']})
                    else:
                        card_urls.append({"name": card['text'], "url": None})

                # 뒤로가기
                await page.go_back(wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)
                section = await page.query_selector("[class*='f_bnr_card_prom']")
                if section:
                    await section.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
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
                                            tag: el.tagName, text,
                                            x: Math.round(rect.left + rect.width / 2),
                                            y: Math.round(rect.top + rect.height / 2),
                                            href: el.href || ''
                                        });
                                    }
                                }
                            });
                            return results;
                        }
                    """)
                    today_cards = cards[:today_count] if today_count > 0 else cards[:2]

            print(f"\n수집된 URL: {card_urls}")

            # 각 URL 접속 후 텍스트 수집
            for i, card in enumerate(card_urls):
                if card['url']:
                    print(f"\n[{i+1}] {card['name']} 접속: {card['url']}")
                    try:
                        await page.goto(card['url'], wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(3)
                        content = await page.evaluate("() => document.body.innerText.slice(0, 800)")
                        print(f"텍스트:\n{content}")
                    except Exception as e:
                        print(f"  오류: {e}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
