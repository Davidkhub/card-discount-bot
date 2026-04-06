#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 카드 클릭 이벤트 디버그")

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

        # 오늘 카드 섹션의 모든 클릭 가능 요소 좌표 찾기
        print("\n오늘 카드 영역 요소 탐색...")
        card_elements = await page.evaluate("""
            () => {
                const results = [];
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const text = el.innerText?.trim();
                    // "즉시할인" 텍스트를 포함한 카드 찾기
                    if (text === '즉시할인') {
                        const rect = el.getBoundingClientRect();
                        // 부모로 올라가면서 클릭 가능한 요소 찾기
                        let clickable = el;
                        for (let i = 0; i < 10; i++) {
                            clickable = clickable.parentElement;
                            if (!clickable) break;
                            const style = window.getComputedStyle(clickable);
                            if (style.cursor === 'pointer' || clickable.tagName === 'A' || clickable.tagName === 'BUTTON') {
                                break;
                            }
                        }
                        const crect = clickable ? clickable.getBoundingClientRect() : rect;
                        results.push({
                            tag: clickable?.tagName,
                            cls: clickable?.className?.toString().slice(0, 60),
                            x: Math.round(crect.left + crect.width / 2),
                            y: Math.round(crect.top + crect.height / 2),
                            width: Math.round(crect.width),
                            height: Math.round(crect.height),
                            parentText: clickable?.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 60)
                        });
                    }
                }
                return results;
            }
        """)

        print(f"즉시할인 요소 {len(card_elements)}개 발견:")
        for i, el in enumerate(card_elements):
            print(f"  [{i}] tag={el['tag']} x={el['x']} y={el['y']} w={el['width']} h={el['height']}")
            print(f"       cls={el['cls'][:50]}")
            print(f"       text='{el['parentText']}'")

        # 첫 번째 카드(오늘) 좌표 클릭
        if card_elements:
            first = card_elements[0]
            print(f"\n첫 번째 카드 좌표 클릭: ({first['x']}, {first['y']})")

            # 새 페이지 열림 감지
            try:
                async with context.expect_page(timeout=5000) as new_page_info:
                    await page.mouse.click(first['x'], first['y'])
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)
                print(f"  새 페이지 URL: {new_page.url}")
                await new_page.screenshot(path="screenshots/hmall_card_detail.png", full_page=True)
                content = await new_page.evaluate("() => document.body.innerText.slice(0, 500)")
                print(f"  내용:\n{content}")

            except Exception as e:
                print(f"  새 페이지 없음: {e}")
                # 현재 페이지 URL 변화 확인
                await page.mouse.click(first['x'], first['y'])
                await asyncio.sleep(3)
                print(f"  클릭 후 URL: {page.url}")
                await page.screenshot(path="screenshots/hmall_card_click.png", full_page=False)
                content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
                print(f"  내용:\n{content}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
