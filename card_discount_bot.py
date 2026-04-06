#!/usr/bin/env python3
import asyncio
import smtplib
import os
import re
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
    results = []

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

        # 카드 섹션 스크롤
        await page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(2)

        # 오늘 카드 수 파악 - 개선된 파싱
        full_text = await page.evaluate("() => document.body.innerText")
        print(f"\n  [디버그] 카드혜택 섹션 텍스트:")

        # "한눈에 보는 카드 혜택" 이후 텍스트 추출
        card_section = ""
        card_match = re.search(r"한눈에 보는 카드 혜택(.+?)오늘의 간편결제", full_text, re.DOTALL)
        if card_match:
            card_section = card_match.group(1)
            print(f"  {card_section[:300]}")

        # 오늘 날짜 패턴 생성 (예: 04.06)
        now = datetime.now()
        today_pattern = f"{now.month:02d}.{now.day:02d}"
        print(f"\n  오늘 날짜 패턴: {today_pattern}")

        # 오늘 날짜 이후 ~ 다음 날짜 이전까지 즉시할인 개수 파악
        today_count = 0
        if card_section:
            # 오늘 날짜 위치 찾기
            today_pos = card_section.find(today_pattern)
            if today_pos == -1:
                # "오늘" 키워드로 fallback
                today_pos = card_section.find("오늘")
            
            if today_pos >= 0:
                after_today = card_section[today_pos:]
                # 다음 날짜 패턴 위치 찾기 (MM.DD 형식)
                next_date = re.search(r"\d{2}\.\d{2}\s*\([월화수목금토일]\)", after_today[5:])
                if next_date:
                    today_section = after_today[: next_date.start() + 5]
                else:
                    today_section = after_today[:500]
                
                today_count = today_section.count("즉시할인")
                print(f"  오늘 섹션 텍스트: {today_section[:200]}")
                print(f"  오늘 카드 수: {today_count}개")

        if today_count == 0:
            today_count = 1
            print("  카드 수 파악 실패 - 1개로 기본값 설정")

        # 카드 요소 좌표 수집
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
        print(f"  오늘 카드 목록: {[c['text'] for c in today_cards]}")

        # 각 카드 URL 수집
        card_urls = []
        for i, card in enumerate(today_cards):
            print(f"\n  [{i+1}] URL 수집: '{card['text']}'")
            await page.mouse.click(card['x'], card['y'])
            await asyncio.sleep(3)
            url = page.url
            print(f"       URL: {url}")

            if url and 'dpl/index' not in url:
                # 카드명 정리
                text = card['text']
                pct_match = re.search(r'(\d+)\s*%', text)
                pct = pct_match.group(1) + "%" if pct_match else ""
                card_name = re.sub(r'즉시할인|\d+\s*%', '', text).strip()
                card_urls.append({"name": card_name, "pct": pct, "url": url})

            # 뒤로가기 후 원상복구
            await page.go_back(wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            await page.evaluate(
                "() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }"
            )
            try:
                el = await page.query_selector("[data-maindispseq='7']")
                if el:
                    await el.click(force=True)
                    await asyncio.sleep(3)
            except Exception:
                pass
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

        print(f"\n  수집된 URL {len(card_urls)}개")

        # 각 URL 접속 → 스크린샷
        for i, card in enumerate(card_urls):
            print(f"\n  [{i+1}] 스크린샷: {card['name']} {card['pct']}")
            try:
                await page.goto(card['url'], wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{today}.png")
                await page.screenshot(path=path, full_page=True)
                print(f"       저장: {path}")
                results.append({
                    "card_name": f"{card['name']} {card['pct']}",
                    "path": path
                })
            except Exception as e:
                print(f"       오류: {e}")

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

    if cj_path and os.path.exists(cj_path):
        cid_map["cj"] = ("img_cj", cj_path)
        cj_block = '<img src="cid:img_cj" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">'
    else:
        cj_block = '<p style="color:#aaa;">수집 실패</p>'

    hmall_blocks = ""
    if hmall_results:
        for i, r in enumerate(hmall_results):
            cid = f"img_hmall_{i}"
            cid_map[f"hmall_{i}"] = (cid, r["path"])
            hmall_blocks += f"""
            <div style="margin-bottom:20px;">
              <p style="font-size:14px;font-weight:600;color:#185FA5;margin:0 0 8px;
                        border-left:3px solid #185FA5;padding-left:8px;">
                {r['card_name']}
              </p>
              <img src="cid:{cid}" style="max-width:100%;border:1px solid #eee;
                                          border-radius:8px;display:block;">
            </div>"""
    else:
        hmall_blocks = '<p style="color:#aaa;">수집 실패</p>'

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
        Hmall — 오늘의 카드할인
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
