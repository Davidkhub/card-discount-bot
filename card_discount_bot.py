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

SITES = {
    "cj": {
        "name": "CJ온스타일",
        "url": "https://display.cjonstyle.com/m/homeTab/main?hmtabMenuId=H00005",
        "selectors": [
            ".benefit_section",
            ".benefit_inner",
            ".lst_benefit",
        ],
    },
}

SCREENSHOT_DIR = "screenshots"


async def capture_site(browser, site_key, cfg):
    page = await browser.new_page(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    try:
        print(f"[{cfg['name']}] 접속 시작")
        await page.goto(cfg["url"], wait_until="networkidle", timeout=40000)
        await asyncio.sleep(5)

        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        path = os.path.join(SCREENSHOT_DIR, f"{site_key}_{today}.png")

        captured = False
        for selector in cfg.get("selectors", []):
            try:
                el = await page.query_selector(selector)
                if el:
                    box = await el.bounding_box()
                    print(f"  셀렉터 [{selector}] 박스: {box}")
                    if box and box["width"] > 50 and box["height"] > 50:
                        await el.screenshot(path=path)
                        print(f"  캡처 성공: {selector}")
                        captured = True
                        break
            except Exception as e:
                print(f"  셀렉터 [{selector}] 오류: {e}")
                continue

        if not captured:
            await page.screenshot(path=path)
            print(f"  fallback: 전체 페이지 캡처")

        print(f"  저장: {path}")
        return path

    except Exception as e:
        print(f"  [{cfg['name']}] 오류: {e}")
        return None
    finally:
        await page.close()


def send_email(screenshots):
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[datetime.now().weekday()]
    subject = f"[카드할인봇] {today_str}({weekday}) 홈쇼핑 카드할인"

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    html_blocks = []
    cid_map = {}

    for site_key, path in screenshots.items():
        name = SITES[site_key]["name"]
        url  = SITES[site_key]["url"]

        if path and os.path.exists(path):
            cid = f"img_{site_key}"
            cid_map[site_key] = (cid, path)
            html_blocks.append(f"""
            <div style="margin-bottom:28px;">
              <h3 style="margin:0 0 10px;font-size:15px;color:#222;
                         border-left:4px solid #E24B4A;padding-left:10px;">
                {name}
              </h3>
              <img src="cid:{cid}"
                   style="max-width:100%;border:1px solid #eee;
                          border-radius:8px;display:block;">
            </div>""")
        else:
            html_blocks.append(f"""
            <div style="margin-bottom:28px;">
              <h3 style="margin:0 0 10px;font-size:15px;color:#999;
                         border-left:4px solid #ccc;padding-left:10px;">
                {name}
              </h3>
              <p style="color:#aaa;font-size:13px;">
                수집 실패 - <a href="{url}">직접 확인하기</a>
              </p>
            </div>""")

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;
                                  margin:0 auto;padding:24px;color:#333;">
      <h2 style="border-bottom:2px solid #eee;padding-bottom:12px;">
        홈쇼핑 카드할인 - {today_str}({weekday})
      </h2>
      {''.join(html_blocks)}
      <p style="font-size:11px;color:#bbb;margin-top:24px;">
        카드할인 봇 자동 발송
      </p>
    </body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    for site_key, (cid, path) in cid_map.items():
        with open(path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline")
            msg.attach(img)

    print(f"이메일 발송 중 -> {TO_EMAIL}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASSWORD)
        smtp.send_message(msg)
    print("발송 완료!")


async def main():
    print(f"카드할인 봇 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    screenshots = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        for key, cfg in SITES.items():
            screenshots[key] = await capture_site(browser, key, cfg)
        await browser.close()

    for key, path in screenshots.items():
        print(f"  {SITES[key]['name']}: {'성공' if path else '실패'}")

    if not GMAIL_USER or not GMAIL_PASSWORD or not TO_EMAIL:
        print("Gmail 환경변수 없음 - 발송 건너뜀")
        return

    send_email(screenshots)
    print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
