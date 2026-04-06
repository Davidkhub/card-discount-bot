#!/usr/bin/env python3
import asyncio
import smtplib
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from playwright.async_api import async_playwright

GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
TO_EMAIL       = os.environ.get("TO_EMAIL", "")
SCREENSHOT_DIR = "screenshots"


async def capture_cj(browser):
    page = await browser.new_page(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    try:
        print("[CJ온스타일] 접속 중...")
        await page.goto(
            "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005",
            wait_until="networkidle", timeout=40000,
        )
        await asyncio.sleep(5)

        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(SCREENSHOT_DIR, f"cj_{today}.png")

        captured = False
        for selector in [".benefit_section", ".benefit_inner", ".lst_benefit"]:
            try:
                el = await page.query_selector(selector)
                if el:
                    box = await el.bounding_box()
                    if box and box["width"] > 50 and box["height"] > 50:
                        await el.screenshot(path=path)
                        print(f"  캡처 성공: {selector}")
                        captured = True
                        break
            except Exception:
                continue

        if not captured:
            await page.screenshot(path=path)
            print("  전체 페이지 캡처 (fallback)")

        return path
    except Exception as e:
        print(f"  오류: {e}")
        return None
    finally:
        await page.close()


async def capture_hmall(context):
    page = await context.new_page()
    results = []  # {"card_name": ..., "path": ...}

    try:
        print("[Hmall] 접속 중...")
        try:
            await page.goto(
                "https://www.hmall.com/md/dpl/index",
                wait_until="domcontentloaded", timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(5)

        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        # 팝업 닫기
        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
        except Exception:
            pass
        await page.evaluate(
            "() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }"
        )
        await asyncio.sleep(1)

        # 혜택 탭 클릭
        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                await el.click(force=True)
                await asyncio.sleep(4)
                print("  혜택 탭 클릭 성공")
        except Exception as e:
            print(f"  혜택 탭 클릭 실패: {e}")

        # 카드 섹션으로 스크롤
        await page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(2)

        # 오늘 카드 요소들 찾기
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

        # 오늘 날짜 카드만 (앞쪽 inViewport 카드들)
        # 텍스트에서 "오늘" 섹션 카드 수 파악 - 첫 번째 날짜 변경 전까지
        today_cards = []
        full_text = await page.evaluate("() => document.body.innerText")
        import re
        match = re.search(r"오늘\s*[\d.]+\s*\([월화수목금토일]\)(.*?)(?=\d{2}\.\d{2}\s*\([월화수목금토일]\)|오늘의 간편결제)", full_text, re.DOTALL)
        today_count = 1
        if match:
            today_text = match.group(1)
            today_count = today_text.count("즉시할인")
            print(f"  오늘 카드 수: {today_count}개")

        today_cards = card_elements[:today_count]
        print(f"  처리할 카드: {[c['text'] for c in today_cards]}")

        # 각 카드 클릭 → 상세 페이지 스크린샷
        for i, card in enumerate(today_cards):
            card_name = card['text'].replace(' 즉시할인', '').strip()
            print(f"\n  [{i+1}/{len(today_cards)}] '{card_name}' 클릭...")

            try:
                await page.mouse.click(card['x'], card['y'])
                await asyncio.sleep(3)

                detail_url = page.url
                print(f"  이동 URL: {detail_url}")

                if 'crdDmndDcPrmo' in detail_url or detail_url != "https://www.hmall.com/md/dpl/index":
                    # 상세 페이지 스크린샷 (전체)
                    path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{today}.png")
                    await page.screenshot(path=path, full_page=True)
                    print(f"  스크린샷 저장: {path}")
                    results.append({"card_name": card_name, "path": path})

                    # 뒤로가기 후 원래 페이지 복원
                    await page.go_back(wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(3)

                    # 팝업 재제거
                    await page.evaluate(
                        "() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }"
                    )

                    # 혜택 탭 재클릭
                    try:
                        el = await page.query_selector("[data-maindispseq='7']")
                        if el:
                            await el.click(force=True)
                            await asyncio.sleep(3)
                    except Exception:
                        pass

                    # 카드 섹션 재스크롤
                    await page.evaluate("window.scrollTo(0, 900)")
                    await asyncio.sleep(2)

                    # 요소 재탐색
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
                                        text: parent?.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 40)
                                    });
                                }
                            });
                            return results;
                        }
                    """)
                    today_cards = card_elements[:today_count]

            except Exception as e:
                print(f"  오류: {e}")

        return results

    except Exception as e:
        print(f"  전체 오류: {e}")
        return []
    finally:
        await page.close()


def send_email(cj_path, hmall_results):
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[datetime.now().weekday()]
    subject = f"[카드할인봇] {today_str}({weekday}) 홈쇼핑 카드할인"

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    cid_map = {}

    # CJ온스타일 블록
    if cj_path and os.path.exists(cj_path):
        cid_map["cj"] = ("img_cj", cj_path)
        cj_block = '<img src="cid:img_cj" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">'
    else:
        cj_block = '<p style="color:#aaa;">수집 실패 - <a href="https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005">직접 확인</a></p>'

    # Hmall 블록
    hmall_blocks = ""
    if hmall_results:
        for i, r in enumerate(hmall_results):
            cid = f"img_hmall_{i}"
            cid_map[f"hmall_{i}"] = (cid, r["path"])
            hmall_blocks += f"""
            <div style="margin-bottom:16px;">
              <p style="font-size:13px;font-weight:600;color:#185FA5;margin:0 0 6px;">{r['card_name']}</p>
              <img src="cid:{cid}" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">
            </div>"""
    else:
        hmall_blocks = '<p style="color:#aaa;">수집 실패 - <a href="https://www.hmall.com/md/dpl/index">직접 확인</a></p>'

    html = f"""<html><body style="font-family:'Malgun Gothic',Arial,sans-serif;
                                  max-width:700px;margin:0 auto;padding:24px;color:#333;">
      <h2 style="border-bottom:2px solid #eee;padding-bottom:12px;font-size:18px;">
        홈쇼핑 카드할인 — {today_str}({weekday})
      </h2>

      <h3 style="font-size:15px;border-left:4px solid #E24B4A;padding-left:10px;margin-bottom:10px;">
        CJ온스타일
      </h3>
      {cj_block}

      <h3 style="font-size:15px;border-left:4px solid #185FA5;padding-left:10px;margin:28px 0 10px;">
        Hmall (현대홈쇼핑) — 오늘의 카드할인
      </h3>
      {hmall_blocks}

      <hr style="border:none;border-top:1px solid #f0f0f0;margin-top:24px;">
      <p style="font-size:11px;color:#bbb;">카드할인 봇 자동 발송</p>
    </body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    for key, (cid, path) in cid_map.items():
        if os.path.exists(path):
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-ID", f"<{cid}>")
                img.add_header("Content-Disposition", "inline")
                msg.attach(img)

    print(f"\n이메일 발송 중 -> {TO_EMAIL}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASSWORD)
        smtp.send_message(msg)
    print("발송 완료!")


async def main():
    import re
    print(f"카드할인 봇 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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

        cj_path = await capture_cj(browser)
        hmall_results = await capture_hmall(context)

        await browser.close()

    print(f"\nCJ온스타일: {'성공' if cj_path else '실패'}")
    print(f"Hmall: {len(hmall_results)}개 카드 수집")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(cj_path, hmall_results)


if __name__ == "__main__":
    asyncio.run(main())
