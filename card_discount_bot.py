#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    print("Hmall 카드탭 클릭 디버그")

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

        # 오늘 카드 탭 요소들 찾기 (알림신청 버튼 기준으로 앞의 카드 찾기)
        print("\n오늘 카드 탭 요소 탐색...")
        card_info = await page.evaluate("""
            () => {
                const results = [];
                // '알림신청' 버튼들을 기준으로 찾기
                document.querySelectorAll('button, a').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text === '알림신청') {
                        // 부모로 올라가서 카드 컨테이너 찾기
                        let parent = el;
                        for (let i = 0; i < 6; i++) {
                            parent = parent.parentElement;
                            if (!parent) break;
                        }
                        if (parent) {
                            results.push({
                                containerText: parent.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 100),
                                containerClass: parent.className?.toString().slice(0, 80),
                                containerTag: parent.tagName,
                                clickable: parent.onclick !== null || parent.tagName === 'A' || parent.tagName === 'BUTTON'
                            });
                        }
                    }
                });
                return results;
            }
        """)
        print(f"알림신청 버튼 기준 카드 컨테이너 {len(card_info)}개:")
        for i, c in enumerate(card_info):
            print(f"  [{i}] tag={c['containerTag']} | text='{c['containerText']}' | cls={c['containerClass'][:50]}")

        # 첫 번째 카드 탭 클릭 시도 (새 페이지 감지)
        print("\n첫 번째 카드 클릭 시도...")
        try:
            # 새 페이지 열림 감지
            async with context.expect_page(timeout=5000) as new_page_info:
                # 오늘 섹션의 첫 번째 클릭 가능 요소 클릭
                today_card = await page.evaluate("""
                    () => {
                        const allEls = document.querySelectorAll('*');
                        for (const el of allEls) {
                            if (el.innerText?.trim() === '알림신청') {
                                let parent = el;
                                for (let i = 0; i < 8; i++) {
                                    parent = parent.parentElement;
                                    if (!parent) break;
                                    if (parent.tagName === 'A' && parent.href && !parent.href.endsWith('#')) {
                                        return { href: parent.href, tag: parent.tagName };
                                    }
                                }
                                break;
                            }
                        }
                        return null;
                    }
                """)
                print(f"  첫 번째 카드 링크: {today_card}")

                if today_card and today_card.get('href'):
                    await page.goto(today_card['href'], wait_until="domcontentloaded", timeout=20000)
                else:
                    # 직접 클릭
                    card_els = await page.query_selector_all('[class*="zk73pr"]')
                    if card_els:
                        await card_els[0].click()
                    else:
                        raise Exception("클릭 대상 없음")

            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            print(f"  새 페이지 URL: {new_page.url}")
            await new_page.screenshot(path="screenshots/hmall_card_detail.png", full_page=True)
            content = await new_page.evaluate("() => document.body.innerText.slice(0, 500)")
            print(f"  내용: {content}")

        except Exception as e:
            print(f"  새 페이지 감지 실패: {e}")
            # 현재 페이지에서 URL 변화 확인
            before_url = page.url
            try:
                card_els = await page.query_selector_all('[class*="zk73pr"]')
                print(f"  zk73pr 클래스 요소 {len(card_els)}개 발견")
                if card_els:
                    await card_els[0].click(force=True)
                    await asyncio.sleep(3)
                    after_url = page.url
                    print(f"  클릭 전 URL: {before_url}")
                    print(f"  클릭 후 URL: {after_url}")
                    await page.screenshot(path="screenshots/hmall_after_card_click.png")
                    content = await page.evaluate("() => document.body.innerText.slice(0, 500)")
                    print(f"  내용: {content}")
            except Exception as e2:
                print(f"  직접 클릭도 실패: {e2}")

        await browser.close()
        print("\n디버그 완료")

if __name__ == "__main__":
    asyncio.run(main())
