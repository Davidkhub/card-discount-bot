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
                                cls: el.className?.toString().slice(0, 60),
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                            });
                        }
                    }
                });
                return results;
            }
        """)
        print(f"  상세 페이지 탭 {len(tabs)}개: {[t['text'] for t in tabs]}")

        for i, tab in enumerate(tabs):
            print(f"  [{i+1}/{len(tabs)}] 탭 클릭: '{tab['text']}'")
            try:
                await page.mouse.click(tab['x'], tab['y'])
                await asyncio.sleep(2)
                path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{today}.png")
                await page.screenshot(path=path, full_page=True)
                print(f"    저장: {path}")
                results.append({"card_name": tab['text'], "path": path})
            except Exception as e:
                print(f"    오류: {e}")
        return results
    except Exception as e:
        print(f"  전체 오류: {e}")
        return []
    finally:
        await page.close()


async def collect_lotte(context):
    """롯데홈쇼핑: 텍스트로 카드 정보 수집"""
    page = await context.new_page()
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
            print("  카드 청구할인 섹션 못 찾음")
            return []

        text = await section.inner_text()
        print(f"  섹션 텍스트:\n{text}")

        # 오늘 카드 파싱
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cards = []
        i = 0
        in_today = False
        while i < len(lines):
            line = lines[i]
            if line == "오늘":
                in_today = True
                i += 1
                continue
            if in_today and re.match(r"^\d+\.\d+", line):
                break  # 내일 날짜 만나면 종료
            if in_today and "청구할인" in lines[i+1] if i+1 < len(lines) else False:
                card_name = line
                discount = ""
                j = i + 1
                while j < len(lines) and j < i + 4:
                    if re.match(r"^\d+%$", lines[j]):
                        discount = lines[j]
                        break
                    j += 1
                if discount:
                    cards.append({"card_name": card_name, "discount": discount})
                    print(f"  카드 파싱: {card_name} {discount}")
            i += 1

        return cards
    except Exception as e:
        print(f"  오류: {e}")
        return []
    finally:
        await page.close()


def make_lotte_card_image(cards):
    """Pillow로 롯데홈쇼핑 카드 이미지 생성"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "Pillow", "--break-system-packages", "-q"])
        from PIL import Image, ImageDraw, ImageFont

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    card_w, card_h = 260, 160
    padding = 20
    total_w = len(cards) * card_w + (len(cards) + 1) * padding
    total_h = card_h + padding * 2 + 50

    img = Image.new("RGB", (total_w, total_h), color="#f5f5f5")
    draw = ImageDraw.Draw(img)

    # 제목
    draw.text((padding, 10), "롯데홈쇼핑 카드 청구할인", fill="#333333")

    colors = ["#333333", "#8B6914", "#1a5276", "#6c3483"]

    for i, card in enumerate(cards):
        x = padding + i * (card_w + padding)
        y = 50

        # 카드 배경
        color = colors[i % len(colors)]
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=12, fill=color)

        # 카드사명
        draw.text((x + 20, y + 20), card["card_name"], fill="white")
        draw.text((x + 20, y + 50), "청구할인", fill="#cccccc")

        # 할인율
        pct = card["discount"]
        draw.text((x + 20, y + 85), pct, fill="white")

    path = os.path.join(SCREENSHOT_DIR, f"lotte_{today}.png")
    img.save(path)
    print(f"  롯데 카드 이미지 생성: {path}")
    return path


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

    # CJ온스타일
    if cj_path and os.path.exists(cj_path):
        cid_map["cj"] = ("img_cj", cj_path)
        cj_block = '<img src="cid:img_cj" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">'
    else:
        cj_block = '<p style="color:#aaa;">수집 실패</p>'

    # Hmall
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

    # 롯데홈쇼핑 - 텍스트 카드 HTML
    lotte_block = ""
    if lotte_cards:
        card_items = ""
        for card in lotte_cards:
            card_items += f"""
            <div style="display:inline-block;background:#333;color:white;
                        border-radius:12px;padding:16px 24px;margin-right:12px;
                        min-width:140px;vertical-align:top;">
              <div style="font-size:13px;color:#ccc;margin-bottom:4px;">{card['card_name']}</div>
              <div style="font-size:12px;color:#aaa;margin-bottom:8px;">청구할인</div>
              <div style="font-size:28px;font-weight:700;">{card['discount']}</div>
            </div>"""
        lotte_block = f'<div style="padding:8px 0;">{card_items}</div>'
    else:
        lotte_block = '<p style="color:#aaa;">수집 실패</p>'

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
      <h3 style="font-size:15px;border-left:4px solid #8B0000;padding-left:10px;margin:28px 0 10px;">
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
        lotte_cards = await collect_lotte(context)

        await browser.close()

    print(f"\nCJ온스타일: {'성공' if cj_path else '실패'}")
    print(f"Hmall: {len(hmall_results)}개 카드")
    print(f"롯데홈쇼핑: {len(lotte_cards)}개 카드 - {lotte_cards}")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(cj_path, hmall_results, lotte_cards)


if __name__ == "__main__":
    asyncio.run(main())
