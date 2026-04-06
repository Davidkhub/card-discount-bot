#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 카드 클릭 후 화면 캡처 디버그")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.hmall.com/md/dpl/index", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"goto 예외 무시: {e}")
        await asyncio.sleep(5)

        os.makedirs("screenshots", exist_ok=True)

        # 팝업 닫기
        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
        except Exception:
            pass
        await page.evaluate("() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }")
        await asyncio.sleep(1)

        # 혜택 탭 클릭
        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                await el.click(force=True)
                await asyncio.sleep(4)
                print("혜택 탭 클릭 성공")
        except Exception as e:
            print(f"혜택 탭 클릭 실패: {e}")

        # 카드 섹션으로 스크롤
        print("카드 섹션으로 스크롤...")
        await page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(2)
        await page.screenshot(path="screenshots/hmall_scrolled.png")
        print("스크롤 후 스크린샷 저장")

        # 오늘 첫 번째 카드 클릭 (x=90, y=1041 → 스크롤 후 y 재계산)
        print("\n오늘 첫 번째 카드 클릭...")
        card_elements = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.innerText?.trim() === '즉시할인') {
                        let parent = el;
                        for (let i = 0; i < 10; i++) {
                            parent = parent.parentElement;
                            if (!parent) break;
                            const style = window.getComputedStyle(parent);
                            if (style.cursor === 'pointer') break;
                        }
                        const rect = parent ? parent.getBoundingClientRect() : el.getBoundingClientRect();
                        results.push({
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            text: parent?.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 40),
                            inViewport: rect.top >= 0 && rect.top <= 844
                        });
                    }
                });
                return results;
            }
        """)

        print(f"카드 요소 {len(card_elements)}개:")
        for i, el in enumerate(card_elements):
            print(f"  [{i}] x={el['x']} y={el['y']} inViewport={el['inViewport']} text='{el['text']}'")

        # 뷰포트 내 첫 번째 카드 클릭
        today_cards = [el for el in card_elements if el['inViewport']]
        if today_cards:
            target = today_cards[0]
            print(f"\n클릭: ({target['x']}, {target['y']}) - '{target['text']}'")
            await page.mouse.click(target['x'], target['y'])
            await asyncio.sleep(3)

            # 화면 변화 캡처
            await page.screenshot(path="screenshots/hmall_after_click.png")
            print("클릭 후 스크린샷 저장")

            # 모달/패널 열렸는지 확인
            modal_info = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="Modal"], [class*="drawer"], [class*="Drawer"], [class*="panel"], [class*="Panel"]');
                    const results = [];
                    dialogs.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            results.push({
                                tag: el.tagName,
                                cls: el.className?.toString().slice(0, 60),
                                text: el.innerText?.trim().slice(0, 200)
                            });
                        }
                    });
                    return results;
                }
            """)
            print(f"\n열린 모달/패널 {len(modal_info)}개:")
            for m in modal_info:
                print(f"  cls={m['cls'][:50]}")
                print(f"  text='{m['text'][:150]}'")

            # URL 변화 확인
            print(f"\n현재 URL: {page.url}")

            # 전체 텍스트 변화 확인
            content = await page.evaluate("() => document.body.innerText.slice(0, 1000)")
            print(f"\n페이지 텍스트:\n{content}")
        else:
            print("뷰포트 내 카드 없음 - 스크롤 조정 필요")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
