#!/usr/bin/env python3
import asyncio
import smtplib
import re
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


# ────────────────────────────────────────────
# CJ온스타일 - 스크린샷 캡처
# ────────────────────────────────────────────
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
            wait_until="networkidle",
            timeout=40000,
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


# ────────────────────────────────────────────
# Hmall - 카드할인 텍스트 수집
# ────────────────────────────────────────────
async def collect_hmall(browser):
    page = await browser.new_page(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    )
    try:
        print("[Hmall] 접속 중...")
        try:
            await page.goto(
                "https://www.hmall.com/md/dpl/index",
                wait_until="domcontentloaded",
                timeout=40000,
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(5)

        # 팝업 닫기
        try:
            el = await page.query_selector("[aria-label='메인 배너 팝업'] button")
            if el:
                await el.click(force=True)
                await asyncio.sleep(1)
                print("  팝업 닫기 성공")
        except Exception:
            pass
        await page.evaluate("() => { document.querySelectorAll('[role=\"dialog\"], #modal-root > *').forEach(el => el.remove()); }")
        await asyncio.sleep(1)

        # 혜택 탭 클릭
        try:
            el = await page.query_selector("[data-maindispseq='7']")
            if el:
                await el.click(force=True)
                print("  혜택 탭 클릭 성공")
                await asyncio.sleep(4)
        except Exception as e:
            print(f"  혜택 탭 클릭 실패: {e}")

        # 전체 텍스트에서 카드혜택 섹션 추출
        full_text = await page.evaluate("() => document.body.innerText")

        # "한눈에 보는 카드 혜택" 섹션 추출
        card_section = ""
        match = re.search(r"한눈에 보는 카드 혜택(.+?)오늘의 간편결제 혜택", full_text, re.DOTALL)
        if match:
            card_section = match.group(1).strip()
            print("  카드혜택 섹션 추출 성공")
        else:
            # 오늘 날짜 기준으로 추출 시도
            today_str = datetime.now().strftime("%-m.%-d")
            match2 = re.search(rf"오늘\s*{re.escape(today_str)}.+?(?=트렌드|더보기|$)", full_text, re.DOTALL)
            if match2:
                card_section = match2.group(0).strip()[:500]
                print("  날짜 기준 추출 성공")
            else:
                card_section = "카드혜택 정보를 추출하지 못했습니다."
                print("  추출 실패")

        print(f"  추출된 내용:\n{card_section[:300]}")
        return card_section

    except Exception as e:
        print(f"  오류: {e}")
        return None
    finally:
        await page.close()


# ────────────────────────────────────────────
# 텍스트 → HTML 변환 (카드혜택 파싱)
# ────────────────────────────────────────────
def parse_hmall_cards(raw_text):
    if not raw_text:
        return "<p style='color:#aaa;'>수집 실패</p>"

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    rows = []
    i = 0
    current_date = "오늘"

    while i < len(lines):
        line = lines[i]
        # 날짜 패턴 (예: 오늘, 04.07 (화))
        if re.match(r"^(오늘|0?\d+\.\d+)", line):
            current_date = line
            i += 1
            continue
        # 알림신청 스킵
        if "알림신청" in line:
            i += 1
            continue
        # 카드사명 + 다음줄에 즉시할인 + 할인율
        if i + 2 < len(lines) and "즉시할인" in lines[i + 1]:
            card_name = line
            discount = lines[i + 2] if i + 2 < len(lines) else ""
            unit = lines[i + 3] if i + 3 < len(lines) and lines[i + 3] == "%" else "%"
            rows.append((current_date, card_name, f"{discount}{unit}"))
            i += 4
            continue
        i += 1

    if not rows:
        # 파싱 실패 시 원문 그대로
        return f"<pre style='font-size:13px;line-height:1.7;'>{raw_text[:800]}</pre>"

    # 오늘 날짜 강조
    html = "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
    html += "<tr style='background:#f5f5f5;'><th style='padding:8px;text-align:left;border-bottom:1px solid #eee;'>날짜</th><th style='padding:8px;text-align:left;border-bottom:1px solid #eee;'>카드사</th><th style='padding:8px;text-align:left;border-bottom:1px solid #eee;'>할인</th></tr>"
    for date, card, discount in rows:
        is_today = "오늘" in date
        bg = "#fff9e6" if is_today else "#fff"
        bold = "font-weight:600;" if is_today else ""
        today_badge = " <span style='background:#E24B4A;color:#fff;font-size:11px;padding:1px 5px;border-radius:3px;'>오늘</span>" if is_today else ""
        html += f"<tr style='background:{bg};'><td style='padding:8px;border-bottom:1px solid #f0f0f0;{bold}'>{date}{today_badge}</td><td style='padding:8px;border-bottom:1px solid #f0f0f0;{bold}'>{card}</td><td style='padding:8px;border-bottom:1px solid #f0f0f0;{bold}color:#E24B4A;'>{discount}</td></tr>"
    html += "</table>"
    return html


# ────────────────────────────────────────────
# 이메일 발송
# ────────────────────────────────────────────
def send_email(cj_path, hmall_text):
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[datetime.now().weekday()]
    subject = f"[카드할인봇] {today_str}({weekday}) 홈쇼핑 카드할인"

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    hmall_html = parse_hmall_cards(hmall_text)
    cj_img_block = ""
    if cj_path and os.path.exists(cj_path):
        cj_img_block = '<img src="cid:img_cj" style="max-width:100%;border:1px solid #eee;border-radius:8px;display:block;">'
    else:
        cj_img_block = '<p style="color:#aaa;">수집 실패 - <a href="https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005">직접 확인</a></p>'

    html = f"""<html><body style="font-family:'Malgun Gothic',Arial,sans-serif;
                                  max-width:700px;margin:0 auto;padding:24px;color:#333;">
      <h2 style="border-bottom:2px solid #eee;padding-bottom:12px;font-size:18px;">
        홈쇼핑 카드할인 — {today_str}({weekday})
      </h2>

      <h3 style="font-size:15px;border-left:4px solid #E24B4A;padding-left:10px;margin-bottom:10px;">
        CJ온스타일
      </h3>
      {cj_img_block}

      <h3 style="font-size:15px;border-left:4px solid #185FA5;padding-left:10px;margin:28px 0 10px;">
        Hmall (현대홈쇼핑) — 일자별 카드할인
      </h3>
      {hmall_html}

      <hr style="border:none;border-top:1px solid #f0f0f0;margin-top:24px;">
      <p style="font-size:11px;color:#bbb;">카드할인 봇 자동 발송</p>
    </body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    if cj_path and os.path.exists(cj_path):
        with open(cj_path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", "<img_cj>")
            img.add_header("Content-Disposition", "inline")
            msg.attach(img)

    print(f"\n이메일 발송 중 -> {TO_EMAIL}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASSWORD)
        smtp.send_message(msg)
    print("발송 완료!")


# ────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────
async def main():
    print(f"카드할인 봇 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        cj_path   = await capture_cj(browser)
        hmall_text = await collect_hmall(browser)
        await browser.close()

    print(f"\nCJ온스타일: {'성공' if cj_path else '실패'}")
    print(f"Hmall: {'성공' if hmall_text else '실패'}")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(cj_path, hmall_text)


if __name__ == "__main__":
    asyncio.run(main())
