import argparse
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


TEXT_VALUES = {
    "prolific_id": "A" * 24,
    "browser_first": "Chrome",
    "can": "red",
    "words": "test",
    "failures_per_q": "test",
    "clicks": "[]",
    "OtherInfoC": "I considered the recent return patterns, the direction of change, and how stable each asset looked across the prior months.",
    "OtherInfoB": "I considered the recent return patterns, the direction of change, and how stable each asset looked across the prior months.",
    "OpenFeedback": "Overall this study was clear and straightforward, and the instructions were easy to follow.",
}

NUMBER_VALUES = {
    "refresh_count": "0",
    "PredictionA": "5",
    "PredictionB": "5",
    "RiskA": "3",
    "RiskB": "3",
    "Confidence": "3",
    "Age": "30",
}

RADIO_VALUES = {
    "lines": "1",
    "cafewall": "2",
    "question_1": "1",
    "question_2": "0",
    "question_3": "1",
    "question_4": "1",
    "question_5": "2",
    "AssetToSell": "A",
    "AssetToBuy": "A",
    "MuM": "3",
    "MuC": "3",
    "LastRetM": "3",
    "LastRetC": "3",
    "Outperform": "3",
    "Riskiness": "3",
    "Recency": "3",
    "MuB": "3",
    "LGFC": "3",
    "LGFB": "3",
    "SigmaHighC": "3",
    "SigmaHighB": "3",
    "SigmaLowC": "3",
    "SigmaLowB": "3",
    "Satisfaction": "5",
    "Sex": "2",
    "FinInterest": "3",
    "Investor": "1",
    "FinanceProf": "0",
    "RiskAffinity": "3",
}


def normalize_url(base_url: str, maybe_relative: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", maybe_relative)


def unique_participant_links(page, base_url: str):
    links = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    results = []
    seen = set()
    for href in links:
        if not href:
            continue
        if "/InitializeParticipant/" not in href:
            continue
        full = normalize_url(base_url, href)
        if full not in seen:
            seen.add(full)
            results.append(full)
    return results


def create_session_and_get_links(page, base_url: str, app_name: str, expected_links: int):
    demo_url = normalize_url(base_url, f"demo/{app_name}")
    page.goto(demo_url, wait_until="domcontentloaded")

    # The demo page uses websocket to create session and redirect.
    try:
        page.wait_for_url(lambda u: f"/demo/{app_name}" not in u, timeout=30000)
    except PlaywrightTimeoutError:
        pass

    links = unique_participant_links(page, base_url)

    # If redirected directly to one participant, keep it as fallback.
    if not links and "/InitializeParticipant/" in page.url:
        links = [page.url]

    if len(links) >= expected_links:
        return links[:expected_links]

    # Fallback: try sessions page create form.
    page.goto(normalize_url(base_url, "sessions"), wait_until="domcontentloaded")
    if page.locator("text=Create new session").count() > 0:
        page.locator("text=Create new session").first.click()

    if page.locator("select[name='session_config']").count() > 0:
        page.select_option("select[name='session_config']", app_name)

    candidates = [
        "input[name='num_participants']",
        "input[name='num-demo-participants']",
        "input[name='num_demo_participants']",
    ]
    for selector in candidates:
        if page.locator(selector).count() > 0:
            page.fill(selector, str(expected_links))
            break

    submit_candidates = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Create')",
        "button:has-text('Start')",
    ]
    for selector in submit_candidates:
        if page.locator(selector).count() > 0:
            page.locator(selector).first.click()
            break

    page.wait_for_load_state("domcontentloaded")
    links = unique_participant_links(page, base_url)
    if links:
        return links[:expected_links]

    matches = re.findall(r"/InitializeParticipant/[A-Za-z0-9]+", page.content())
    urls = []
    seen = set()
    for m in matches:
        full = normalize_url(base_url, m)
        if full not in seen:
            seen.add(full)
            urls.append(full)
    if urls:
        return urls[:expected_links]

    raise RuntimeError(
        f"Could not find participant links automatically. Open /demo/{app_name} once in browser, then rerun."
    )


def safe_page_label(url: str):
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        page_name = parts[-2]
        return page_name
    return "page"


def resolve_page_label(page) -> str:
    """Resolve a stable page label from URL, with survey-page DOM fallbacks."""
    label = safe_page_label(page.url)

    # Prefer URL-based detection for the survey pages so they are never skipped
    # if the DOM changes or if the page content is still loading.
    if "Survey1" in page.url:
        return "Survey1"
    if "Survey2" in page.url:
        return "Survey2"
    if "Survey3" in page.url:
        return "Survey3"

    # Survey pages are critical in output; detect by field signatures so
    # captures stay correctly named even if URL labels are unexpected.
    if page.locator("textarea[name='OtherInfoC'], textarea[name='OtherInfoB']").count() > 0:
        return "Survey1"

    if page.locator("input[name='MuM'], input[name='Recency']").count() > 0:
        return "Survey2"

    if page.locator("input[name='Age'], input[name='RiskAffinity']").count() > 0:
        return "Survey3"

    return label


def set_hidden_defaults(page):
    if page.locator("input[name='failed_comprehension_test']").count() > 0:
        page.eval_on_selector(
            "input[name='failed_comprehension_test']",
            "el => { el.value = 'False'; }",
        )


def fill_fields(page):
    set_hidden_defaults(page)
    radio_values = dict(RADIO_VALUES)

    # Comprehension answers depend on treatment; read them from page JS when available.
    if "ComprehensionTestPage" in page.url:
        try:
            dynamic_answers = page.evaluate(
                "() => (typeof correctAnswers !== 'undefined' ? correctAnswers : null)"
            )
            if isinstance(dynamic_answers, dict):
                for k, v in dynamic_answers.items():
                    radio_values[str(k)] = str(v)
        except Exception:
            pass

    # Fill textareas
    for ta in page.locator("textarea[name]").all():
        name = ta.get_attribute("name")
        if not name:
            continue
        try:
            if not ta.is_visible():
                continue
        except Exception:
            continue
        value = TEXT_VALUES.get(name, "test")
        ta.fill(value)

    # Fill selects
    for sel in page.locator("select[name]").all():
        name = sel.get_attribute("name")
        if not name:
            continue
        value = radio_values.get(name)
        if value is not None:
            try:
                sel.select_option(value=value)
                continue
            except Exception:
                pass
        options = sel.locator("option").all()
        fallback = None
        for opt in options:
            v = opt.get_attribute("value")
            if v:
                fallback = v
                break
        if fallback is not None:
            sel.select_option(value=fallback)

    # Fill text/number style inputs
    for inp in page.locator(
        "input[name]:not([type='radio']):not([type='checkbox']):not([type='hidden']):not([type='submit'])"
    ).all():
        name = inp.get_attribute("name")
        if not name:
            continue
        input_type = (inp.get_attribute("type") or "text").lower()
        if input_type in {"number", "range"}:
            value = NUMBER_VALUES.get(name, "3")
        else:
            value = TEXT_VALUES.get(name)
            if value is None:
                value = NUMBER_VALUES.get(name, "test")
        inp.fill(value)

    if "Task_ReturnPrediction" in page.url:
        for name in ["RiskA", "RiskB", "Confidence"]:
            visual_selector = f"#{name}-visual"
            hidden_selector = f"#{name}"
            if page.locator(visual_selector).count() > 0:
                value = NUMBER_VALUES.get(name, "3")
                page.eval_on_selector(
                    visual_selector,
                    "(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }",
                    value,
                )
            if page.locator(hidden_selector).count() > 0:
                page.eval_on_selector(
                    hidden_selector,
                    "(el, value) => { el.value = value; }",
                    NUMBER_VALUES.get(name, "3"),
                )

    # Choose radio values by name
    radio_names = page.eval_on_selector_all(
        "input[type='radio'][name]",
        "els => [...new Set(els.map(e => e.name))]",
    )
    for name in radio_names:
        preferred = radio_values.get(name)
        if preferred is not None and page.locator(
            f"input[type='radio'][name='{name}'][value='{preferred}']"
        ).count() > 0:
            selector = f"input[type='radio'][name='{name}'][value='{preferred}']"
            try:
                page.check(selector, force=True)
            except Exception:
                page.eval_on_selector(
                    selector,
                    "el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }",
                )
            continue

        first_radio = page.locator(f"input[type='radio'][name='{name}']").first
        if first_radio.count() > 0:
            try:
                first_radio.check(force=True)
            except Exception:
                first_radio.evaluate(
                    "el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }"
                )

    # Keep leave unchecked so flow continues.
    if page.locator("input[type='checkbox'][name='leave']").count() > 0:
        page.uncheck("input[type='checkbox'][name='leave']")


def next_button_locator(page):
    candidates = [
        "button.otree-btn-next",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Next')",
        "button:has-text('Continue')",
    ]
    for selector in candidates:
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc.first
    return None


def advance_internal_page(page):
    if page.locator("#nextMonthBtn").count() > 0:
        next_month = page.locator("#nextMonthBtn")
        final_next = page.locator("#finalNextBtn")

        if final_next.count() > 0 and final_next.is_visible():
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                    final_next.click()
            except PlaywrightTimeoutError:
                final_next.click()
            return True

        if next_month.is_visible():
            next_month.click()
            return True

    return False


def force_advance_form(page):
    try:
        page.evaluate(
            """
            () => {
                const form = document.querySelector('form');
                if (form) {
                    form.submit();
                    return true;
                }
                const nextButton = document.querySelector('button.otree-btn-next, button[type="submit"], input[type="submit"]');
                if (nextButton) {
                    nextButton.click();
                    return true;
                }
                return false;
            }
            """
        )
        return True
    except Exception:
        return False


def fast_forward_bot_screening(page):
    """Bypass the BotScreening page in automation.

    The page uses a reCAPTCHA widget that is not practical to solve in an
    automated screenshot run. We try a few DOM-level ways to trigger the
    normal next-page submission without waiting on the hidden UI button.
    """
    try:
        page.evaluate(
            """
            () => {
                try {
                    if (typeof enableBtn === 'function') {
                        enableBtn();
                    }
                } catch (e) {}

                const btn = document.querySelector('button.otree-btn-next, button[type="submit"], input[type="submit"]');
                const form = document.querySelector('form');
                const recaptcha = document.querySelector('textarea[name="g-recaptcha-response"]');

                if (recaptcha) {
                    recaptcha.value = 'automation-bypass';
                    recaptcha.dispatchEvent(new Event('input', { bubbles: true }));
                    recaptcha.dispatchEvent(new Event('change', { bubbles: true }));
                }

                if (btn) {
                    btn.style.display = 'block';
                    btn.removeAttribute('disabled');
                }

                if (btn) {
                    try {
                        btn.click();
                    } catch (e) {}
                }

                if (form) {
                    try {
                        form.submit();
                    } catch (e) {}
                }
            }
            """
        )
    except Exception:
        return False

    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass

    return True


def capture_page(page, target: Path):
    # Prefer content containers to avoid large blank areas in full-page shots.
    selectors = [
        "div.otree-body",
        "main",
        "form",
        "div.container",
        "body",
    ]
    for selector in selectors:
        loc = page.locator(selector).first
        if loc.count() > 0:
            try:
                loc.screenshot(path=str(target))
                return
            except Exception:
                pass

    page.screenshot(path=str(target), full_page=False)


def run_participant(
    page,
    participant_url: str,
    out_dir: Path,
    treatment_id: int,
    max_steps: int,
    capture_once_labels: set[str] | None = None,
    already_captured_once: set[str] | None = None,
):
    page.goto(participant_url, wait_until="domcontentloaded")
    seen_labels = set()
    capture_once_labels = capture_once_labels or set()
    already_captured_once = already_captured_once if already_captured_once is not None else set()

    for step in range(1, max_steps + 1):
        page.wait_for_load_state("domcontentloaded")
        label = resolve_page_label(page)
        if label not in seen_labels:
            should_capture = not (
                label in capture_once_labels and label in already_captured_once
            )

            if should_capture:
                file_name = f"{len(seen_labels) + 1:03d}_{label}.png"
                target = out_dir / f"treatment_{treatment_id:02d}" / file_name
                target.parent.mkdir(parents=True, exist_ok=True)
                capture_page(page, target)
                if label in capture_once_labels:
                    already_captured_once.add(label)
            seen_labels.add(label)

        if advance_internal_page(page):
            continue

        if label == "BotScreening":
            if fast_forward_bot_screening(page):
                continue

        btn = next_button_locator(page)
        if btn is None:
            break

        fill_fields(page)
        url_before_click = page.url
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                btn.click()
        except PlaywrightTimeoutError:
            # Some pages may update in place. Avoid double-clicking unless URL truly stayed the same.
            if page.url == url_before_click:
                try:
                    btn.click()
                    page.wait_for_url(lambda u: u != url_before_click, timeout=5000)
                except Exception:
                    if not force_advance_form(page):
                        break
            if page.url == url_before_click:
                if not advance_internal_page(page) and not force_advance_form(page):
                    break

        if "LinkToProlific" in page.url:
            # capture thank-you page and stop
            page.wait_for_load_state("domcontentloaded")
            label = resolve_page_label(page)
            file_name = f"{step+1:03d}_{label}.png"
            target = out_dir / f"treatment_{treatment_id:02d}" / file_name
            capture_page(page, target)
            break


def main():
    parser = argparse.ArgumentParser(description="Capture ME screenshots for treatments 1-16")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--app", default="ME")
    parser.add_argument("--treatments", type=int, default=16)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--out", default="screenshots")
    parser.add_argument(
        "--capture-once-labels",
        default="BotScreening",
        help="Comma-separated page labels to screenshot once across all treatments (default: BotScreening)",
    )
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    out_root = Path(args.out)
    app_out_name = f"{args.app}_treatments"
    out_dir = out_root if out_root.name == app_out_name else out_root / app_out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    capture_once_labels = {
        label.strip() for label in args.capture_once_labels.split(",") if label.strip()
    }
    already_captured_once = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})

        participant_links = create_session_and_get_links(
            page=page,
            base_url=args.base_url,
            app_name=args.app,
            expected_links=args.treatments,
        )

        for idx, participant_url in enumerate(participant_links[: args.treatments], start=1):
            run_page = browser.new_page(viewport={"width": 1440, "height": 1100})
            run_participant(
                page=run_page,
                participant_url=participant_url,
                out_dir=out_dir,
                treatment_id=idx,
                max_steps=args.max_steps,
                capture_once_labels=capture_once_labels,
                already_captured_once=already_captured_once,
            )
            run_page.close()

        page.close()
        browser.close()

    print(f"Saved screenshots under: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
