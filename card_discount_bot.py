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
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
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
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/lotte_main.png", full_page=False)
        print(f"메인 스크린샷 저장 / URL: {page.url}")

        # 팝업 닫기 시도
        print("\n팝업 닫기 시도...")
        for selector in [
            "[aria-label='닫기']",
            "button[class*='close']",
            "button[class*='Close']",
            ".btn_close",
            ".pop_close",
            "[class*='popup'] button",
        ]:
            try:
                el = await page.query_selector(selector)
                if el:
                    await el.click(force=True)
                    print(f"  팝업 닫기: {selector}")
                    await asyncio.sleep(1)
            except Exception:
                pass

        await page.screenshot(path="screenshots/lotte_no_popup.png", full_page=False)

        # "카드 청구할인" 영역 찾기
        print("\n카드 청구할인 영역 탐색...")
        card_info = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && (
                        text.includes('카드 청구할인') ||
                        text.includes('청구할인') ||
                        text.includes('카드할인')
                    ) && text.length < 200) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            tag: el.tagName,
                            cls: el.className?.toString().slice(0, 60),
                            text: text.slice(0, 80),
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                        });
                    }
                });
                return results.slice(0, 20);
            }
        """)
        print(f"카드 청구할인 관련 요소 {len(card_info)}개:")
        for el in card_info:
            print(f"  [{el['tag']}] text='{el['text']}' x={el['x']} y={el['y']} w={el['width']} cls={el['cls'][:40]}")

        # 오늘 카드 클릭 가능 요소 찾기
        print("\n오늘 카드 클릭 요소 탐색...")
        today_cards = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && text.includes('청구할인') && text.includes('%') && text.length < 50) {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (rect.width > 30 && rect.height > 30) {
                            results.push({
                                tag: el.tagName,
                                cls: el.className?.toString().slice(0, 60),
                                text,
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                                cursor: style.cursor,
                                href: el.href || ''
                            });
                        }
                    }
                });
                return results.slice(0, 10);
            }
        """)
        print(f"오늘 카드 요소 {len(today_cards)}개:")
        for el in today_cards:
            print(f"  [{el['tag']}] '{el['text']}' x={el['x']} y={el['y']} cursor={el['cursor']} href={el['href'][:60]}")

        # 첫 번째 카드 클릭 시도
        if today_cards:
            target = today_cards[0]
            print(f"\n첫 번째 카드 클릭: ({target['x']}, {target['y']})")
            await page.mouse.click(target['x'], target['y'])
            await asyncio.sleep(3)
            print(f"클릭 후 URL: {page.url}")
            await page.screenshot(path="screenshots/lotte_after_click.png", full_page=False)

            # 탭 구조 확인
            tabs = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('a, button, li').forEach(el => {
                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                        if (text && text.includes('%') && text.length < 30) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                results.push({
                                    tag: el.tagName,
                                    text,
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
            print(f"\n클릭 후 탭 목록 ({len(tabs)}개):")
            for t in tabs:
                print(f"  [{t['tag']}] '{t['text']}' x={t['x']} y={t['y']} cls={t['cls'][:40]}")

            content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
            print(f"\n페이지 텍스트:\n{content}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
