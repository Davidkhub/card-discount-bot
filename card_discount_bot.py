async def capture_hmall(browser):
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "Pillow", "--break-system-packages", "-q"])
    from PIL import Image

    page = await browser.new_page(
        viewport={"width": 390, "height": 844},
        user_agent=MOB_UA,
    )
    results = []
    try:
        print("[Hmall] 접속 중...")
        try:
            await page.goto(
                f"https://www.hmall.com/md/dpl/index?_={datetime.now().strftime('%Y%m%d%H%M%S')}",
                wait_until="domcontentloaded", timeout=40000
            )
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
        print(f"  상세 페이지 URL: {page.url}")

        tabs = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('a, button, li, div[role="tab"]').forEach(el => {
                    const text = el.innerText?.trim().replace(/\s+/g, ' ');
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

        if len(tabs) == 0:
            print("  탭 없음 - 현재 페이지 단일 카드로 스크린샷")
            path = os.path.join(SCREENSHOT_DIR, f"hmall_0_{today}.png")
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            await page.screenshot(path=path, full_page=False)
            card_name = first['text'].replace('즉시할인', '').strip()
            results.append({"card_name": card_name, "path": path})
            return results

        async def screenshot_full_scroll(tab_index):
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            scroll_height = await page.evaluate("() => document.body.scrollHeight")
            viewport_h = 844
            shot_paths = []
            sy = 0
            shot_idx = 0
            while sy < scroll_height:
                await page.evaluate(f"window.scrollTo(0, {sy})")
                await asyncio.sleep(0.4)
                tmp = os.path.join(SCREENSHOT_DIR, f"hmall_tmp_{tab_index}_s{shot_idx}_{today}.png")
                await page.screenshot(path=tmp, full_page=False)
                shot_paths.append((sy, tmp))
                sy += viewport_h
                shot_idx += 1

            if len(shot_paths) == 1:
                final_path = os.path.join(SCREENSHOT_DIR, f"hmall_{tab_index}_{today}.png")
                os.rename(shot_paths[0][1], final_path)
                return final_path

            pieces = []
            for sy_val, tmp_path in shot_paths:
                img = Image.open(tmp_path)
                remaining = scroll_height - sy_val
                if remaining < viewport_h:
                    img = img.crop((0, 0, img.width, remaining))
                pieces.append((sy_val, img))

            total_w = pieces[0][1].width
            combined = Image.new("RGB", (total_w, scroll_height))
            for sy_val, img in pieces:
                combined.paste(img, (0, sy_val))

            final_path = os.path.join(SCREENSHOT_DIR, f"hmall_{tab_index}_{today}.png")
            combined.save(final_path)
            for _, img in pieces:
                img.close()
            for _, tmp_path in shot_paths:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            print(f"    합치기 완료: {combined.size}")
            return final_path

        for i, tab in enumerate(tabs):
            print(f"  [{i+1}/{len(tabs)}] 탭 클릭: '{tab['text']}'")
            try:
                await page.evaluate(f"""
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

                # ── 디버그: 실제 body 텍스트 200자 출력 ──
                page_text = await page.evaluate("() => document.body.innerText.slice(0, 200)")
                print(f"    [DEBUG] body 앞 200자: {repr(page_text)}")

                # 403 체크 제거 → 일단 무조건 캡처
                final_path = await screenshot_full_scroll(i)
                results.append({"card_name": tab['text'], "path": final_path})
                print(f"    저장: {final_path}")

            except Exception as e:
                print(f"    오류: {e}")
                import traceback; traceback.print_exc()

        return results
    except Exception as e:
        print(f"  전체 오류: {e}")
        return []
    finally:
        await page.close()
