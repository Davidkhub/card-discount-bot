#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("롯데홈쇼핑 카드청구할인 요소 직접 캡처")

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

        # f_bnr_card_prom 클래스로 직접 요소 찾기
        print("\n카드 청구할인 요소 직접 캡처...")
        section = await page.query_selector("[class*='f_bnr_card_prom']")
        if section:
            path = "screenshots/lotte_card_section.png"
            await section.screenshot(path=path, timeout=60000)
            print(f"  섹션 스크린샷 저장: {path}")

            # 섹션 내 텍스트
            text = await section.inner_text()
            print(f"  섹션 텍스트:\n{text}")

            # 오늘 카드 클릭 요소 찾기 (섹션 내부)
            cards = await page.evaluate("""
                () => {
                    const section = document.querySelector("[class*='f_bnr_card_prom']");
                    if (!section) return [];
                    const results = [];
                    section.querySelectorAll('a, button, li, div').forEach(el => {
                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                        if (text && text.includes('청구할인') && text.includes('%') && text.length < 30) {
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            if (rect.width > 30 && rect.height > 30) {
                                results.push({
                                    tag: el.tagName,
                                    text,
                                    x: Math.round(rect.left + rect.width / 2),
                                    y: Math.round(rect.top + rect.height / 2),
                                    cls: el.className?.toString().slice(0, 60),
                                    cursor: style.cursor,
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
                print(f"  [{c['tag']}] '{c['text']}' x={c['x']} y={c['y']} cursor={c['cursor']} href={c['href'][:60]}")

            # 첫 번째 카드 클릭
            if cards:
                target = cards[0]
                print(f"\n첫 번째 카드 클릭: ({target['x']}, {target['y']})")
                await page.mouse.click(target['x'], target['y'])
                await asyncio.sleep(3)
                print(f"클릭 후 URL: {page.url}")

                # 클릭 후 새 요소 확인 (모달/상세)
                modal = await page.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="layer"], [class*="popup"]');
                        const results = [];
                        dialogs.forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 100 && rect.height > 100) {
                                    results.push({
                                        tag: el.tagName,
                                        cls: el.className?.toString().slice(0, 60),
                                        text: el.innerText?.trim().slice(0, 200),
                                        x: Math.round(rect.x),
                                        y: Math.round(rect.y),
                                        w: Math.round(rect.width),
                                        h: Math.round(rect.height),
                                    });
                                }
                            }
                        });
                        return results;
                    }
                """)
                print(f"\n클릭 후 모달/레이어 {len(modal)}개:")
                for m in modal:
                    print(f"  [{m['tag']}] cls={m['cls'][:40]} w={m['w']} h={m['h']}")
                    print(f"  text='{m['text'][:150]}'")

                # 모달이 있으면 요소 스크린샷
                if modal:
                    for i, m in enumerate(modal[:3]):
                        el = await page.query_selector(f"[class*='{m['cls'].split()[0]}']")
                        if el:
                            await el.screenshot(path=f"screenshots/lotte_modal_{i}.png", timeout=30000)
                            print(f"  모달 스크린샷 저장: lotte_modal_{i}.png")
        else:
            print("f_bnr_card_prom 요소 못 찾음")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
