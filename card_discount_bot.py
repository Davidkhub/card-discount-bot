async def capture_hmall(browser):
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "Pillow", "--break-system-packages", "-q"])
    from PIL import Image

    context = await browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=MOB_UA,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
        }
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
        window.chrome = { runtime: {} };
    """)

    page = await context.new_page()
    results = []
    try:
        print("[Hmall] 접속 중...")
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        # 1단계: 메인 방문으로 쿠키 확보
        try:
            await page.goto("https://www.hmall.com/", wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"  메인 goto 예외 무시: {e}")
        await asyncio.sleep(3)
        await page.evaluate("window.scrollTo(0, 500)")
        await asyncio.sleep(1)

        # 2단계: 혜택 탭 페이지
        try:
            await page.goto(
                f"https://www.hmall.com/md/dpl/index?_={datetime.now().strftime('%Y%m%d%H%M%S')}",
                wait_until="domcontentloaded", timeout=40000
            )
        except Exception as e:
            print(f"  goto 예외 무시: {e}")
        await asyncio.sleep(5)

        # 팝업 제거
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

        # 즉시할인 카드 클릭 → 네트워크 요청에서 상세 URL 캡처
        detail_url = None

        async def handle_request(request):
            nonlocal detail_url
            if "crdDmndDcPrmo" in request.url or "prmoNo" in request.url:
                detail_url = request.url
                print(f"  [네트워크] 상세 URL 감지: {request.url}")

        page.on("request", handle_request)

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
                            text: parent?.innerText?.trim().replace(/\s+/g, ' ').slice(0, 40)
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
        await asyncio.sleep(4)
        print(f"  현재 URL: {page.url}")

        page.remove_listener("request", handle_request)

        # 현재 URL이 상세 페이지인지 확인
        current_url = page.url
        if "crdDmndDcPrmo" in current_url or "prmoNo" in current_url:
            detail_url = current_url

        print(f"  상세 URL: {detail_url}")

        # 상세 URL을 못 잡았으면 JS로 history 확인
        if not detail_url:
            js_url = await page.evaluate("() => location.href")
            print(f"  JS location.href: {js_url}")
            if "crdDmndDcPrmo" in js_url or "prmoNo" in js_url:
                detail_url = js_url

        if not detail_url:
            print("  상세 URL 확보 실패")
            return []

        # 3단계: 상세 페이지를 새 탭에서 직접 goto (Referer 포함)
        detail_page = await context.new_page()
        await detail_page.set_extra_http_headers({
            "Referer": "https://www.hmall.com/md/dpl/index",
        })
        try:
            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print(f"  상세 페이지 goto 예외 무시: {e}")
        await asyncio.sleep(4)

        check = await detail_page.evaluate("() => document.body.innerText.slice(0, 150)")
        print(f"  [DEBUG] 상세 body: {repr(check)}")
        if "403 ERROR" in check:
            print("  상세 페이지 403 - 실패")
            await detail_page.close()
            return []

        # 탭 수집
        tabs = await detail_page.evaluate("""
            () => {
                const results = [];
                const seen = new Set();
                document.querySelectorAll('a, button, li, div[role="tab"]').forEach(el => {
                    const text = el.innerText?.trim().replace(/\s+/g, ' ');
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
        print(f"  탭 {len(tabs)}개: {[t['text'] for t in tabs]}")

        async def screenshot_full_scroll(pg, tab_index):
            await pg.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            scroll_height = await pg.evaluate("() => document.body.scrollHeight")
            viewport_h = 844
            pieces = []
            sy = 0
            idx = 0
            while sy < scroll_height:
                await pg.evaluate(f"window.scrollTo(0, {sy})")
                await asyncio.sleep(0.4)
                tmp = os.path.join(SCREENSHOT_DIR, f"hmall_tmp_{tab_index}_{idx}_{today}.png")
                await pg.screenshot(path=tmp, full_page=False)
                img = Image.open(tmp)
                remaining = scroll_height - sy
                if remaining < viewport_h:
                    img = img.crop((0, 0, img.width, remaining))
                pieces.append(img.copy())
                img.close()
                os.remove(tmp)
                sy += viewport_h
                idx += 1

            if len(pieces) == 1:
                final_path = os.path.join(SCREENSHOT_DIR, f"hmall_{tab_index}_{today}.png")
                pieces[0].save(final_path)
                return final_path

            total_w = pieces[0].width
            total_h = sum(p.height for p in pieces)
            combined = Image.new("RGB", (total_w, total_h))
            y_off = 0
            for p in pieces:
                combined.paste(p, (0, y_off))
                y_off += p.height
            final_path = os.path.join(SCREENSHOT_DIR, f"hmall_{tab_index}_{today}.png")
            combined.save(final_path)
            print(f"    합치기 완료: {combined.size}")
            return final_path

        if len(tabs) == 0:
            print("  탭 없음 - 현재 페이지 단일 캡처")
            path = await screenshot_full_scroll(detail_page, 0)
            results.append({"card_name": first['text'].replace('즉시할인', '').strip(), "path": path})
            await detail_page.close()
            return results

        for i, tab in enumerate(tabs):
            print(f"  [{i+1}/{len(tabs)}] 탭 클릭: '{tab['text']}'")
            try:
                await detail_page.evaluate(f"""
                    () => {{
                        const tabs = [...document.querySelectorAll('a, button, li, div[role="tab"]')]
                            .filter(el => {{
                                const text = el.innerText?.trim().replace(/\s+/g, ' ');
                                return text && text.length < 30 && /%/.test(text);
                            }});
                        if (tabs[{i}]) tabs[{i}].scrollIntoView({{block: 'center', inline: 'center'}});
                        if (tabs[{i}]) tabs[{i}].click();
                    }}
                """)
                await asyncio.sleep(3)

                # 403 체크: "403 ERROR" 문자열 전체로만 판단
                body_start = await detail_page.evaluate("() => document.body.innerText.slice(0, 50)")
                if "403 ERROR" in body_start:
                    print(f"    403 감지 - 건너뜀")
                    continue

                final_path = await screenshot_full_scroll(detail_page, i)
                results.append({"card_name": tab['text'], "path": final_path})
                print(f"    저장: {final_path}")

            except Exception as e:
                print(f"    오류: {e}")
                import traceback; traceback.print_exc()

        await detail_page.close()
        return results

    except Exception as e:
        print(f"  전체 오류: {e}")
        import traceback; traceback.print_exc()
        return []
    finally:
        await page.close()
        await context.close()
