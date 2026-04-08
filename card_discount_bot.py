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

PC_UA  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MOB_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"


async def capture_cj(browser):
    page = await browser.new_page(
        viewport={"width": 1280, "height": 900},
        user_agent=PC_UA,
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


async def capture_hmall(browser):
    page = await browser.new_page(
        viewport={"width": 390, "height": 844},
        user_agent=MOB_UA,
    )
    results = []
    try:
        print("[Hmall] 접속 중...")
        try:
            await page.goto("https://www.hmall.com/md/dpl/index", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(5)
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
        except Exception:
            pass
        await page.evaluate("() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }")
        await asyncio.sleep(1)

        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                await el.click(force=True)
                await asyncio.sleep(4)
                print("  혜택 탭 클릭 성공")
        except Exception as e:
            print(f"  혜택 탭 클릭 실패: {e}")

        await page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(2)

        card_elements = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.innerText?.trim() === '즉시할인') {
                        let parent = el;
                        for (let i = 0; i < 10; i++) {
                            parent = parent.parentElement;
                            if (!parent) break;
                            if (window.getComputedStyle(parent).cursor === 'pointer') break;
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

        if not card_elements:
            print("  카드 요소 없음")
            return []

        first = card_elements[0]
        print(f"  첫 번째 카드 클릭: '{first['text']}'")
        await page.mouse.click(first['x'], first['y'])
        await asyncio.sleep(3)
        print(f"  상세 페이지 URL: {page.url}")

        tabs = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('a, button, li, div[role="tab"]').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && text.length < 30 && /%/.test(text)) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
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
        print(f"  탭 {len(tabs)}개: {[t['text'] for t in tabs]}")

        for i, tab in enumerate(tabs):
            print(f"  [{i+1}/{len(tabs)}] 탭 클릭: '{tab['text']}'")
            try:
                await page.mouse.click(tab['x'], tab['y'])
                await asyncio.sleep(4)
                path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{today}.png")
                await page.screenshot(path=path, full_page=True)
                results.append({"card_name": tab['text'], "path": path})
            except Exception as e:
                print(f"    오류: {e}")

        return results
    except Exception as e:
        print(f"  전체 오류: {e}")
        return []
    finally:
        await page.close()


async def collect_lotte(browser):
    page = await browser.new_page(
        viewport={"width": 1280, "height": 900},
        user_agent=PC_UA,
    )
    try:
        print("[롯데홈쇼핑] 접속 중...")

        async def block_fonts(route):
            if route.request.resource_type == "font":
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_fonts)

        try:
            await page.goto("https://www.lotteimall.com/", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(6)

        for selector in [".btn_close", ".pop_close", "[class*='close']", "[aria-label='닫기']"]:
            try:
                els = await page.query_selector_all(selector)
                for el in els:
                    if await el.is_visible():
                        await el.click(force=True)
                        await asyncio.sleep(0.3)
            except Exception:
                pass

        section = await page.query_selector("[class*='f_bnr_card_prom']")
        if not section:
            print("  카드 섹션 못 찾음")
            return []

        text = await section.inner_text()
        print(f"  섹션 텍스트:\n{text}")

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cards = []
        in_today = False
        for i, line in enumerate(lines):
            if line == "오늘":
                in_today = True
                continue
            if in_today and re.match(r"^\d+\.\d+", line):
                break
            if in_today and line == "청구할인":
                card_name = lines[i - 1] if i > 0 else ""
                pct = lines[i + 1] if i + 1 < len(lines) and re.match(r"^\d+%$", lines[i + 1]) else ""
                if card_name and not re.match(r"^\d+\.\d+", card_name) and card_name != "오늘":
                    if not any(c["card_name"] == card_name for c in cards):
                        cards.append({"card_name": card_name, "discount": pct})
                        print(f"  카드 파싱: {card_name} {pct}")

        if not cards:
            print("  파싱 실패")
            return []

        await section.scroll_into_view_if_needed()
        await asyncio.sleep(2)
        await page.evaluate("""
            () => {
                const section = document.querySelector("[class*='f_bnr_card_prom']");
                const link = section?.querySelector('a');
                if (link) link.click();
            }
        """)
        await asyncio.sleep(3)
        detail_url = page.url
        print(f"  상세 페이지 URL: {detail_url}")

        if "viewMain" in detail_url or "lotteimall.com" not in detail_url:
            print("  상세 페이지 이동 실패 - 텍스트 정보만 발송")
            return cards

        tabs = await page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a, button, li').forEach(el => {
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                    if (text && text.length < 15 && (
                        text.includes('롯데') || text.includes('KB') ||
                        text.includes('현대') || text.includes('삼성') ||
                        text.includes('신한') || text.includes('하나') ||
                        text.includes('마이롯데')
                    )) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 30 && rect.height > 10 && !seen.has(text)) {
                            seen.add(text);
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
        print(f"  상세 탭 {len(tabs)}개: {[t['text'] for t in tabs]}")

        for i, tab in enumerate(tabs):
            print(f"  [{i+1}/{len(tabs)}] 탭 클릭: '{tab['text']}'")
            try:
                await page.mouse.click(tab['x'], tab['y'])
                await asyncio.sleep(2)
                detail = await page.evaluate("""
                    () => {
                        for (const sel of ['.event_cont', '.card_cont', '#contents', 'main', '.cont_area']) {
                            const el = document.querySelector(sel);
                            if (el) return el.innerText.trim().slice(0, 800);
                        }
                        return document.body.innerText.trim().slice(0, 800);
                    }
                """)
                for card in cards:
                    if card["card_name"] in tab["text"] or tab["text"] in card["card_name"]:
                        card["detail"] = detail
                        break
                print(f"    수집 완료")
            except Exception as e:
                print(f"    오류: {e}")

        return cards

    except Exception as e:
        print(f"  전체 오류: {e}")
        return []
    finally:
        await page.close()


def make_lotte_html(lotte_cards):
    if not lotte_cards:
        return '<p style="color:#aaa;">수집 실패</p>'

    card_colors = ["#C0392B", "#D4AC0D", "#1A5276", "#117A65", "#6C3483"]
    cards_html = ""

    for i, card in enumerate(lotte_cards):
        color = card_colors[i % len(card_colors)]
        pct = card.get("discount", "")
        detail_rows = ""
        detail = card.get("detail", "")
        if detail:
            lines = [l.strip() for l in detail.splitlines() if l.strip()]
            for j, line in enumerate(lines):
                if "행사내용" in line and j + 1 < len(lines):
                    detail_rows += f'<tr><td style="color:#999;font-size:11px;padding:2px 0;width:60px;">내용</td><td style="font-size:11px;padding:2px 0;">{lines[j+1][:70]}</td></tr>'
                elif "할인한도" in line and j + 1 < len(lines):
                    detail_rows += f'<tr><td style="color:#999;font-size:11px;padding:2px 0;">한도</td><td style="font-size:11px;padding:2px 0;">{lines[j+1][:50]}</td></tr>'

        cards_html += f"""
        <div style="display:inline-block;vertical-align:top;margin-right:12px;margin-bottom:12px;
                    width:195px;border-radius:12px;overflow:hidden;border:1px solid #eee;">
          <div style="background:{color};padding:16px 20px;">
            <div style="font-size:13px;color:rgba(255,255,255,0.8);margin-bottom:2px;">{card['card_name']}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-bottom:10px;">청구할인</div>
            <div style="font-size:30px;font-weight:700;color:#fff;">{pct}</div>
          </div>
          <div style="background:#fff;padding:10px 14px;">
            <table style="width:100%;border-collapse:collapse;">{detail_rows if detail_rows else '<tr><td style="font-size:11px;color:#aaa;">-</td></tr>'}</table>
          </div>
        </div>"""

    return f'<div style="padding:4px 0;">{cards_html}</div>'


def send_email(cj_path, hmall_results, lotte_cards):
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
            <div style="margin-bottom:16px;">
              <p style="font-size:13px;font-weight:600;color:#185FA5;margin:0 0 6px;
                        border-left:3px solid #185FA5;padding-left:8px;">{r['card_name']}</p>
              <img src="cid:{cid}" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">
            </div>"""
    else:
        hmall_blocks = '<p style="color:#aaa;">수집 실패</p>'

    lotte_block = make_lotte_html(lotte_cards)

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
      <h3 style="font-size:15px;border-left:4px solid #C0392B;padding-left:10px;margin:28px 0 10px;">
        롯데홈쇼핑 — 오늘의 카드 청구할인
      </h3>
      {lotte_block}
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

        cj_path       = await capture_cj(browser)
        hmall_results = await capture_hmall(browser)
        lotte_cards   = await collect_lotte(browser)

        await browser.close()

    print(f"\nCJ온스타일: {'성공' if cj_path else '실패'}")
    print(f"Hmall: {len(hmall_results)}개 카드")
    print(f"롯데홈쇼핑: {len(lotte_cards)}개 카드 - {[c['card_name'] for c in lotte_cards]}")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(cj_path, hmall_results, lotte_cards)


if __name__ == "__main__":
    asyncio.run(main())
