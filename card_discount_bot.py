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

PC_UA  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MOB_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

VIEWPORT_H  = 844
CROP_TOP    = 50   # CJ 상단 고정 네비게이션 바
CROP_BOTTOM = 60   # CJ 하단 고정 탭 바


# ──────────────────────────────────────────────
# CJ온스타일
# ──────────────────────────────────────────────
async def capture_cj(browser):
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "Pillow", "--break-system-packages", "-q"])
    from PIL import Image

    EFFECTIVE_H = VIEWPORT_H - CROP_TOP - CROP_BOTTOM  # 실제 유효 높이 = 734px

    page = await browser.new_page(
        viewport={"width": 390, "height": VIEWPORT_H},
        user_agent=MOB_UA,
    )
    try:
        print("[CJ온스타일] 접속 중...")
        await page.goto(
            "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00009",
            wait_until="networkidle", timeout=40000,
        )
        await asyncio.sleep(5)
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(SCREENSHOT_DIR, f"cj_{today}.png")

        # 천천히 맨 아래로 스크롤 (lazy-load 트리거)
        print("  천천히 스크롤 중...")
        total_height = await page.evaluate("() => document.body.scrollHeight")
        pos = 0
        while pos < total_height:
            pos += 300
            await page.evaluate(f"window.scrollTo(0, {pos})")
            await asyncio.sleep(0.5)
            total_height = await page.evaluate("() => document.body.scrollHeight")
        await asyncio.sleep(2)

        doc_height = await page.evaluate("() => document.body.scrollHeight")
        bottom_scroll = doc_height - VIEWPORT_H
        print(f"  맨 아래 scrollY: {bottom_scroll}, 문서 총 높이: {doc_height}")

        # 캡처 범위: 맨 아래에서 750px 올라간 지점부터 위로 2800px
        cap_bottom = doc_height - 750
        cap_top    = max(0, cap_bottom - 2800)
        cap_height = cap_bottom - cap_top
        print(f"  캡처 범위: y={cap_top} ~ y={cap_bottom} ({cap_height}px)")

        # EFFECTIVE_H 단위로 스크롤하며 캡처 (상하단 고정 UI 바 제외)
        cropped_imgs = []
        scroll_y = cap_top
        while scroll_y < cap_bottom:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(0.6)

            # 유효 영역 절대 y
            abs_top    = scroll_y + CROP_TOP
            abs_bottom = scroll_y + VIEWPORT_H - CROP_BOTTOM
            actual_top    = max(cap_top, abs_top)
            actual_bottom = min(cap_bottom, abs_bottom)
            if actual_bottom <= actual_top:
                scroll_y += EFFECTIVE_H
                continue

            tmp_path = os.path.join(SCREENSHOT_DIR, f"cj_tmp_{scroll_y}_{today}.png")
            await page.screenshot(path=tmp_path)

            img = Image.open(tmp_path)
            crop_top_px    = actual_top - scroll_y
            crop_bottom_px = actual_bottom - scroll_y
            cropped = img.crop((0, crop_top_px, img.width, crop_bottom_px))
            cropped_imgs.append(cropped)
            img.close()
            os.remove(tmp_path)

            scroll_y += EFFECTIVE_H

        print(f"  {len(cropped_imgs)}구간 캡처 완료: {[img.size for img in cropped_imgs]}")

        total_w = cropped_imgs[0].width
        total_h = sum(img.height for img in cropped_imgs)
        combined = Image.new("RGB", (total_w, total_h))
        y_offset = 0
        for img in cropped_imgs:
            combined.paste(img, (0, y_offset))
            y_offset += img.height
        combined.save(path)
        print(f"  합치기 완료: {combined.size}")
        return path

    except Exception as e:
        print(f"  오류: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        await page.close()


# ──────────────────────────────────────────────
# Hmall (hmall.it 카드 행사 페이지 파싱)
# ──────────────────────────────────────────────
async def collect_hmall(browser):
    page = await browser.new_page(
        viewport={"width": 390, "height": 844},
        user_agent=MOB_UA,
    )
    try:
        print("[Hmall] 접속 중... (hmall.it/m/?cont=card)")
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

        try:
            await page.goto(
                "https://hmall.it/m/?cont=card",
                wait_until="networkidle", timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(4)

        body_start = await page.evaluate("() => document.body.innerText.slice(0, 50)")
        if "403 ERROR" in body_start:
            print("  403 - 수집 불가")
            return []

        # 페이지 전체 텍스트 수집
        full_text = await page.evaluate("() => document.body.innerText")
        print(f"  텍스트 길이: {len(full_text)}")

        today_str = datetime.now().strftime("%Y-%m-%d")

        # "오늘" 키워드 블록 찾기 (다음 날짜 또는 광고 문구 전까지)
        today_match = re.search(
            r'오늘\s*\t+(.*?)(?=\n\d{4}-\d{2}-\d{2}|\n아래 내용|\n이벤트 홈|\Z)',
            full_text, re.DOTALL
        )
        today_content = today_match.group(1) if today_match else ""
        print(f"  오늘 블록: {repr(today_content[:300])}")

        cards = []
        if today_content:
            for line in today_content.splitlines():
                line = line.strip().strip("\t")
                m = re.match(r'(.+?)\s+(\d+)\s*%\s*할인', line)
                if m:
                    card_name = m.group(1).strip()
                    pct       = m.group(2) + "%"
                    # 조건 줄 찾기 (바로 다음 줄)
                    detail = ""
                    idx = today_content.splitlines().index(line) if line in today_content else -1
                    lines_list = today_content.splitlines()
                    for k, l in enumerate(lines_list):
                        if l.strip().strip("\t") == line and k + 1 < len(lines_list):
                            next_line = lines_list[k + 1].strip()
                            if next_line and "%" not in next_line and "카드 할인" not in next_line:
                                detail = next_line
                            break
                    cards.append({
                        'card_name': card_name,
                        'discount':  f"즉시할인 {pct}",
                        'period':    today_str,
                        'limit':     '',
                        'details':   [detail] if detail else [],
                    })
                    print(f"  카드 파싱: {card_name} / {pct} / {detail}")

        if not cards:
            print("  오늘 블록 없음 또는 파싱 실패")

        print(f"  총 {len(cards)}개 카드 수집")
        return cards

    except Exception as e:
        print(f"  전체 오류: {e}")
        import traceback; traceback.print_exc()
        return []
    finally:
        await page.close()


# ──────────────────────────────────────────────
# 롯데홈쇼핑
# ──────────────────────────────────────────────
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
                const excluded = ['마이롯데', '마이페이지', '홈', '장바구니'];
                document.querySelectorAll('a, button, li').forEach(el => {
                    const text = el.innerText?.trim().replace(/\s+/g, ' ');
                    if (text && text.length < 15 &&
                        !excluded.includes(text) && (
                        text.includes('롯데') || text.includes('KB') ||
                        text.includes('현대') || text.includes('삼성') ||
                        text.includes('신한') || text.includes('하나') ||
                        text.includes('NH') || text.includes('농협') ||
                        text.includes('비씨') || text.includes('BC') ||
                        text.includes('카드')
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

        if not tabs:
            print("  탭 없음 - 현재 페이지 텍스트 수집")
            detail = await page.evaluate("() => document.body.innerText.trim().slice(0, 800)")
            for card in cards:
                card["detail"] = detail
            return cards

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


# ──────────────────────────────────────────────
# HTML 생성
# ──────────────────────────────────────────────
def make_hmall_html(hmall_cards):
    if not hmall_cards:
        return '<p style="color:#aaa;">수집 실패</p>'

    card_colors = ["#185FA5", "#1A5276", "#2E86C1", "#117A65", "#6C3483"]
    cards_html = ""

    for i, card in enumerate(hmall_cards):
        color = card_colors[i % len(card_colors)]
        detail_rows = ""
        if card.get('period'):
            detail_rows += f'<tr><td style="color:#999;font-size:11px;padding:2px 0;width:40px;">기간</td><td style="font-size:11px;padding:2px 0;">{card["period"]}</td></tr>'
        if card.get('limit'):
            detail_rows += f'<tr><td style="color:#999;font-size:11px;padding:2px 0;">한도</td><td style="font-size:11px;padding:2px 0;">{card["limit"][:40]}</td></tr>'
        for d in card.get('details', [])[:2]:
            detail_rows += f'<tr><td style="color:#999;font-size:11px;padding:2px 0;">조건</td><td style="font-size:11px;padding:2px 0;">{d[:40]}</td></tr>'

        discount_text = card.get('discount', '')
        pct_match = re.search(r'\d+%', discount_text)
        pct = pct_match.group() if pct_match else '-'

        cards_html += f"""
        <div style="display:inline-block;vertical-align:top;margin-right:12px;margin-bottom:12px;
                    width:195px;border-radius:12px;overflow:hidden;border:1px solid #eee;">
          <div style="background:{color};padding:16px 20px;">
            <div style="font-size:13px;color:rgba(255,255,255,0.8);margin-bottom:2px;">{card['card_name']}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-bottom:10px;">즉시할인</div>
            <div style="font-size:30px;font-weight:700;color:#fff;">{pct}</div>
          </div>
          <div style="background:#fff;padding:10px 14px;">
            <table style="width:100%;border-collapse:collapse;">{detail_rows if detail_rows else '<tr><td style="font-size:11px;color:#aaa;">-</td></tr>'}</table>
          </div>
        </div>"""

    return f'<div style="padding:4px 0;">{cards_html}</div>'


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


# ──────────────────────────────────────────────
# 이메일 발송
# ──────────────────────────────────────────────
def send_email(cj_path, hmall_cards, lotte_cards):
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

    hmall_block = make_hmall_html(hmall_cards)
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
      {hmall_block}

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


# ──────────────────────────────────────────────
# main
# ──────────────────────────────────────────────
async def main():
    print(f"카드할인 봇 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )

        cj_path     = await capture_cj(browser)
        hmall_cards = await collect_hmall(browser)
        lotte_cards = await collect_lotte(browser)

        await browser.close()

    print(f"\nCJ온스타일: {'성공' if cj_path else '실패'}")
    print(f"Hmall: {len(hmall_cards)}개 카드 - {[c['card_name'] for c in hmall_cards]}")
    print(f"롯데홈쇼핑: {len(lotte_cards)}개 카드 - {[c['card_name'] for c in lotte_cards]}")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(cj_path, hmall_cards, lotte_cards)


if __name__ == "__main__":
    asyncio.run(main())
