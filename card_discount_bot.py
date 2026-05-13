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

VIEWPORT_H = 844  # 뷰포트 높이


async def capture_cj(browser):
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "Pillow", "--break-system-packages", "-q"])

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

        # 맨 아래 scrollY 확인
        bottom_scroll = await page.evaluate("() => document.body.scrollHeight - window.innerHeight")
        print(f"  맨 아래 scrollY: {bottom_scroll}")

        # ── CJ 3단 캡처 ──────────────────────────────────────────────
        # 캡처 기준점: 맨 아래에서 360px 위
        # 1) 기준점에서 위로 750px (즉 scrollY = bottom_scroll - 360 - 750 + VIEWPORT_H)
        #    → 화면에 기준점이 하단에 오도록 scrollTo(bottom_scroll - 360)
        # 구조:
        #   shot1: scrollY = bottom_scroll - 360 - (750 - VIEWPORT_H) ... 기준점이 화면 하단
        #   shot2: 기준점 바로 위 360px → scrollY = shot1_scrollY - 360
        #   shot3: 그 위 360px → scrollY = shot2_scrollY - 360
        # 실제로는 viewport 단위 스크린샷이므로, 원하는 픽셀 범위를 crop 해서 합침.

        # 캡처 포인트 정의 (각 구간의 상단 절대 y)
        # 구간: [bottom_scroll+VIEWPORT_H - 360 - 750, ..., bottom_scroll+VIEWPORT_H - 360]
        # 즉 절대 하단 = bottom_scroll + VIEWPORT_H (=document.body.scrollHeight)
        doc_bottom = bottom_scroll + VIEWPORT_H  # 문서 총 높이와 동일

        # 캡처 구간 (절대 y 기준)
        # 맨 아래에서 360px 위 = doc_bottom - 360  → 이 지점 위로 750px
        seg_bottom = doc_bottom - 360          # 캡처 최하단 절대y
        seg_top    = seg_bottom - 750          # 캡처 최상단 절대y (750px 범위)

        # 3개 구간 (위→아래 순서로 정렬, 각 360px)
        # shot A: seg_top ~ seg_top+360
        # shot B: seg_top+360 ~ seg_top+720  (=seg_bottom-30 이지만 360px씩)
        # shot C: 기준점 위 360px → seg_bottom-360 ~ seg_bottom  (= seg_top+390 ~ ...)
        # 단순하게: 3구간 각 360px
        # A: [seg_top,       seg_top+360)
        # B: [seg_top+360,   seg_top+720)   → 마지막 30px은 seg_bottom(750=360+360+30)
        # 750px를 정확히 3등분하지 않으므로 요청대로:
        #   "기준점 위 750px" 전체 + "그 위 360px" + "또 그 위 360px"
        # 총 범위: 750 + 360 + 360 = 1470px
        #   shot1 (맨 아래): seg_bottom-750 ~ seg_bottom  (750px)
        #   shot2 (중간):    seg_bottom-750-360 ~ seg_bottom-750  (360px)
        #   shot3 (맨 위):   seg_bottom-750-720 ~ seg_bottom-750-360  (360px)

        def scroll_for_region(region_top, region_bottom):
            """region이 화면에 들어오도록 scrollY 계산 (region이 뷰포트 중앙 or 상단)"""
            # region을 가능하면 뷰포트 상단에 맞춤
            return max(0, region_top)

        regions = [
            # (절대 top, 절대 bottom, 파일명)
            (seg_bottom - 750 - 720, seg_bottom - 750 - 360, f"cj_s3_{today}.png"),  # 맨 위
            (seg_bottom - 750 - 360, seg_bottom - 750,        f"cj_s2_{today}.png"),  # 중간
            (seg_bottom - 750,       seg_bottom,               f"cj_s1_{today}.png"),  # 맨 아래
        ]

        from PIL import Image

        cropped_imgs = []
        for (reg_top, reg_bottom, fname) in regions:
            reg_top    = max(0, reg_top)
            reg_bottom = max(reg_top, reg_bottom)
            height_px  = reg_bottom - reg_top

            # 스크롤: region_top이 뷰포트 상단에 오도록
            scroll_y = reg_top
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(0.8)

            tmp_path = os.path.join(SCREENSHOT_DIR, fname)
            await page.screenshot(path=tmp_path)

            # crop: 뷰포트 기준으로 region이 시작하는 오프셋
            offset_in_viewport = reg_top - scroll_y  # = 0 (항상)
            img = Image.open(tmp_path)
            crop_top    = offset_in_viewport
            crop_bottom = min(crop_top + height_px, img.height)
            cropped = img.crop((0, crop_top, img.width, crop_bottom))
            cropped_imgs.append(cropped)
            os.remove(tmp_path)

        print(f"  3구간 캡처 완료: {[img.size for img in cropped_imgs]}")

        # 위→아래 순으로 세로 합치기 (regions가 이미 위→아래 순)
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


async def capture_hmall(browser):
    """현대홈쇼핑 카드할인 수집.
    메인 혜택 탭 → 즉시할인 카드 목록 파싱 → 각 카드 상세 URL 직접 접속.
    """
    results = []
    today = datetime.now().strftime("%Y%m%d")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # ── 1단계: 메인 페이지에서 카드 목록 URL 수집 ──────────────────
    page = await browser.new_page(
        viewport={"width": 390, "height": 844},
        user_agent=MOB_UA,
    )
    card_links = []
    try:
        print("[Hmall] 접속 중...")
        await page.goto(
            "https://www.hmall.com/md/dpl/index",
            wait_until="domcontentloaded", timeout=40000,
        )
        await asyncio.sleep(5)

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
                print("  혜택 탭 클릭 성공")
        except Exception as e:
            print(f"  혜택 탭 클릭 실패: {e}")

        await page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(2)

        # 즉시할인 카드 링크 수집
        card_links = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.innerText?.trim() === '즉시할인') {
                        let parent = el;
                        for (let i = 0; i < 10; i++) {
                            parent = parent?.parentElement;
                            if (!parent) break;
                            if (parent.tagName === 'A' && parent.href) {
                                results.push({ href: parent.href, text: parent.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 60) });
                                break;
                            }
                        }
                        if (!results.length || results[results.length-1].href === undefined) {
                            // href 없으면 data-prmo-no 등 탐색
                        }
                    }
                });
                return results;
            }
        """)

        if not card_links:
            # href 방식 실패 시 prmoNo 속성 탐색
            card_links = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('[data-prmo-no], [data-prmo]').forEach(el => {
                        const prmo = el.dataset.prmoNo || el.dataset.prmo;
                        if (prmo) {
                            results.push({
                                href: `https://www.hmall.com/md/eva/crdDmndDcPrmo?prmoNo=${prmo}`,
                                text: el.innerText?.trim().replace(/\\s+/g, ' ').slice(0, 60)
                            });
                        }
                    });
                    return results;
                }
            """)

        # 그래도 없으면 클릭해서 URL 추출
        if not card_links:
            card_elements = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('*').forEach(el => {
                        if (el.innerText?.trim() === '즉시할인') {
                            let parent = el;
                            for (let i = 0; i < 10; i++) {
                                parent = parent?.parentElement;
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

            for elem in card_elements[:3]:
                print(f"  카드 클릭해서 URL 수집: '{elem['text']}'")
                await page.mouse.click(elem['x'], elem['y'])
                await asyncio.sleep(3)
                url = page.url
                if "hmall.com" in url and "index" not in url:
                    card_links.append({"href": url, "text": elem['text']})
                    print(f"    URL: {url}")
                await page.go_back(wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)

        print(f"  수집된 카드 링크 {len(card_links)}개: {[c['text'][:30] for c in card_links]}")

    except Exception as e:
        print(f"  메인 접속 오류: {e}")
    finally:
        await page.close()

    if not card_links:
        print("  카드 링크 없음 - 종료")
        return []

    # ── 2단계: 각 카드 상세 페이지 별도 탭으로 접속 & 스크린샷 ────
    for i, card in enumerate(card_links):
        page2 = await browser.new_page(
            viewport={"width": 390, "height": 844},
            user_agent=MOB_UA,
        )
        try:
            url = card['href']
            print(f"  [{i+1}/{len(card_links)}] 상세 접속: {url}")
            await page2.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

            # 403 / 에러 페이지 확인
            page_text = await page2.evaluate("() => document.body.innerText.slice(0, 300)")
            if "403" in page_text or "request could not be satisfied" in page_text.lower() or "접근" in page_text[:50]:
                print(f"    접근 오류 감지, PC UA로 재시도...")
                await page2.close()
                page2 = await browser.new_page(
                    viewport={"width": 1280, "height": 900},
                    user_agent=PC_UA,
                )
                await page2.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                page_text = await page2.evaluate("() => document.body.innerText.slice(0, 300)")
                if "403" in page_text or "request could not be satisfied" in page_text.lower():
                    print(f"    재시도 후도 에러 - 건너뜀")
                    continue

            # 내부 탭 확인 (카드별 탭이 있는 경우)
            inner_tabs = await page2.evaluate("""
                () => {
                    const seen = new Set();
                    const results = [];
                    document.querySelectorAll('a, button, li, div[role="tab"]').forEach(el => {
                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                        if (text && text.length < 30 && /%/.test(text) && !seen.has(text)) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
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

            if inner_tabs:
                print(f"    내부 탭 {len(inner_tabs)}개: {[t['text'] for t in inner_tabs]}")
                for j, tab in enumerate(inner_tabs):
                    try:
                        await page2.evaluate(f"""
                            () => {{
                                const tabs = [...document.querySelectorAll('a, button, li, div[role="tab"]')]
                                    .filter(el => {{
                                        const text = el.innerText?.trim().replace(/\\s+/g, ' ');
                                        return text && text.length < 30 && /%/.test(text);
                                    }});
                                if (tabs[{j}]) {{ tabs[{j}].scrollIntoView({{block:'center',inline:'center'}}); tabs[{j}].click(); }}
                            }}
                        """)
                        await asyncio.sleep(3)
                        path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{j}_{today}.png")
                        await page2.screenshot(path=path, full_page=True)
                        results.append({"card_name": tab['text'], "path": path})
                        print(f"    탭[{j}] '{tab['text']}' 저장")
                    except Exception as e:
                        print(f"    탭[{j}] 오류: {e}")
            else:
                path = os.path.join(SCREENSHOT_DIR, f"hmall_{i}_{today}.png")
                await page2.screenshot(path=path, full_page=True)
                card_name = card['text'].replace('즉시할인', '').strip() or f"카드{i+1}"
                results.append({"card_name": card_name, "path": path})
                print(f"    단일 저장: {card_name}")

        except Exception as e:
            print(f"    오류: {e}")
        finally:
            await page2.close()

    return results


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
                    const text = el.innerText?.trim().replace(/\\s+/g, ' ');
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
