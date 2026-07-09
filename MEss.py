"""
capture_me_screenshots.py
=========================
Automated Playwright screenshot script for the ME oTree experiment
(single-risky-asset portfolio experiment, 16 treatments x 8 rounds).

Adapted from the CS1 capture script. Key differences vs CS1:
  * No personas. ME's branching is fully treatment-driven (choice vs belief,
    sell vs repurchase, monthly vs since-purchase), so the 16 treatments ARE
    the coverage matrix. One participant slot per treatment.
  * ME has three JS-heavy pages the generic fill/next loop can't drive:
      - AssetsPerformance   : must click "Next month" 11x to reveal the
                              real submit button (#finalNextBtn).
      - Task_ReturnPrediction: PredictionA number + two custom sliders
                              (RiskA, Confidence) gated by JS sliderTouched.
      - ComprehensionTestPage: JS blocks submit unless answers are correct;
                              answers depend on treatment.
  * Per-round pages (AssetsPerformance, task pages, Round_End) repeat 8x;
    they are screenshotted once per treatment (round 1) via seen_labels.

HOW TO USE
----------
1. pip install playwright && playwright install chromium
2. Start oTree:  otree devserver
3. Set SESSION_CONFIG_NAME below to your ME session config (in settings.py).
4. Set TESTING_MODE (see note below), then run:  python capture_me_screenshots.py
5. Review screenshots, then:  otree resetdb

TESTING_MODE
------------
Creates the session with session-config field  testing = <TESTING_MODE>.
  True  -> every page shows a "Skip for testing" button. Navigation is
           bulletproof, but the button appears in your screenshots.
  False -> clean screenshots (no skip button). This script fills all fields
           and drives the custom JS pages manually, so False works too and
           is the right choice for publication/appendix images.
Default is False (clean). Flip to True only if a page won't advance.
"""

import argparse
import json as _json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


# ===========================================================================
# Config
# ===========================================================================
BASE_URL            = "http://localhost:8000/"
APP_NAME            = "ME"        # name_in_url / app folder
SESSION_CONFIG_NAME = "ME"        # <-- must match a config in settings.py SESSION_CONFIGS
NUM_TREATMENTS      = 16          # 1..16, assigned by (id_in_session-1) % 16 + 1
NUM_ROUNDS          = 8
MAX_STEPS           = 400
OUT_DIR             = "screenshots"
HEADED              = True
TESTING_MODE        = True
# ---------------------------------------------------------------------------
# Treatment metadata (mirrors creating_session / set_payoffs in __init__.py)
# ---------------------------------------------------------------------------
MONTHLY_TREATMENTS  = {1, 2, 3, 4, 9, 10, 11, 12}     # else: returns-since-purchase
CHOICE_TREATMENTS   = {1, 3, 5, 7, 9, 11, 13, 15}     # else: belief/prediction
SELL_TREATMENTS     = {1, 2, 5, 6, 9, 10, 13, 14}     # else: repurchase/buy


def treatment_label(t):
    ret   = "monthly" if t in MONTHLY_TREATMENTS else "sincePurchase"
    task  = "choice"  if t in CHOICE_TREATMENTS  else "belief"
    trade = "sell"    if t in SELL_TREATMENTS    else "repurchase"
    return f"{ret}_{task}_{trade}"


# ---------------------------------------------------------------------------
# Comprehension answer keys (question_1..4 correct option index).
# Copied verbatim from ComprehensionTestPage.html's correctAnswers blocks.
# ---------------------------------------------------------------------------
COMPREHENSION_KEYS = {
    1:  (1, 0, 0, 0), 9:  (1, 0, 0, 0),
    5:  (1, 1, 0, 0), 13: (1, 1, 0, 0),
    3:  (1, 0, 1, 1), 11: (1, 0, 1, 1),
    7:  (1, 1, 1, 1), 15: (1, 1, 1, 1),
    2:  (1, 0, 2, 2), 10: (1, 0, 2, 2),
    6:  (1, 1, 2, 2), 14: (1, 1, 2, 2),
    4:  (1, 0, 2, 2), 12: (1, 0, 2, 2),
    8:  (1, 1, 2, 2), 16: (1, 1, 2, 2),
}


# ---------------------------------------------------------------------------
# Field fill tables (ME player fields)
# ---------------------------------------------------------------------------
TEXT_VALUES = {
    "prolific_id":   "A" * 24,
    "browser_first": "Chrome",       # normally JS-set + hidden; harmless if present
    "can":           "red",          # PageB1 attention check
    "words":         "test",         # PageB2 attention check
    "OtherInfoC":    "I considered the asset's past monthly returns.",
    "OtherInfoB":    "I considered the asset's average return.",
    "OpenFeedback":  "The study was clear and well structured.",
    "clicks":        "[]",
}

NUMBER_VALUES = {
    "Age":          "35",
    "PredictionA":  "5",
    "refresh_count": "0",
    # Sliders (0-10 range) handled separately, but keep a fallback:
    "RiskA":        "7",
    "Confidence":   "7",
}

# Radio / select fields -> chosen value. question_1..4 are injected per treatment.
RADIO_VALUES = {
    "lines":        "1",
    "cafewall":     "1",
    "Sex":          "1",
    "FinInterest":  "3",
    "Investor":     "1",
    "FinanceProf":  "0",
    "RiskAffinity": "3",
    "Satisfaction": "3",
    # Survey2 reliance battery
    "MuM": "3", "MuC": "3", "LastRetM": "3", "LastRetC": "3",
    "Outperform": "3", "Riskiness": "3", "Recency": "3",
    # Investment decision: keep/repurchase the asset (value 'A')
    "AssetToSell": "A",
    "AssetToBuy":  "A",
}


# Pages that look identical across treatments -> capture once globally.
CAPTURE_ONCE_LABELS = {
    "Instructions0", "Leave", "PageA1", "PageA2", "PageA3",
    "PageB1", "PageB2", "BotScreening", "Survey3", "LinkToProlific",
}


# ---------------------------------------------------------------------------
# URL / session helpers  (reused from CS1)
# ---------------------------------------------------------------------------
def normalize_url(base_url, maybe_relative):
    return urljoin(base_url.rstrip("/") + "/", maybe_relative)


def unique_participant_links(page, base_url):
    links = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    results, seen = [], set()
    for href in links:
        if not href or "/InitializeParticipant/" not in href:
            continue
        full = normalize_url(base_url, href)
        if full not in seen:
            seen.add(full)
            results.append(full)
    return results


def create_session_and_get_links(page, base_url, config_name, expected_links, testing):
    """REST API -> admin page -> demo page fallback chain."""
    api_url = normalize_url(base_url, "api/sessions")
    try:
        page.goto(base_url, wait_until="domcontentloaded")
        response = page.request.post(
            api_url,
            data=_json.dumps({
                "session_config_name": config_name,
                "num_participants": expected_links,
                "modified_session_config_fields": {"testing": testing},
            }),
            headers={"Content-Type": "application/json"},
        )
        if response.ok:
            body = response.json()
            session_code = body.get("code") or body.get("session_code")
            if session_code:
                lresp = page.request.get(
                    normalize_url(base_url, f"api/sessions/{session_code}/participants")
                )
                if lresp.ok:
                    urls = []
                    for pt in lresp.json():
                        token = pt.get("_url_param") or pt.get("code")
                        if token:
                            urls.append(normalize_url(base_url, f"InitializeParticipant/{token}"))
                    if len(urls) >= expected_links:
                        print(f"  [session] REST API -> {session_code}")
                        return urls[:expected_links]
                page.goto(normalize_url(base_url, f"SessionMonitor/{session_code}"),
                          wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                links = unique_participant_links(page, base_url)
                if len(links) >= expected_links:
                    print(f"  [session] REST API + monitor scrape -> {session_code}")
                    return links[:expected_links]
    except Exception as e:
        print(f"  [session] REST API failed ({e}), trying admin page...")

    for admin_path in ["sessions", "create_session"]:
        try:
            page.goto(normalize_url(base_url, admin_path), wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            for btn_text in ["Create new session", "Create session", "New session"]:
                btn = page.locator(f"text={btn_text}").first
                if btn.count() > 0:
                    btn.click()
                    page.wait_for_load_state("domcontentloaded")
                    break
            if page.locator("select[name='session_config']").count() > 0:
                page.select_option("select[name='session_config']", config_name)
                page.wait_for_timeout(500)
            filled = False
            for sel in ["input[name='num_participants']", "input[name='num-demo-participants']",
                        "input[name='num_demo_participants']", "input[type='number']"]:
                if page.locator(sel).count() > 0:
                    page.fill(sel, str(expected_links))
                    filled = True
                    break
            if not filled:
                continue
            for sel in ["button[type='submit']", "input[type='submit']",
                        "button:has-text('Create')", "button:has-text('Start')"]:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click()
                    break
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            links = unique_participant_links(page, base_url)
            if links:
                print(f"  [session] Admin page /{admin_path}")
                return links[:expected_links]
        except Exception as e:
            print(f"  [session] Admin page /{admin_path} failed ({e})")

    raise RuntimeError(
        f"Could not create a '{config_name}' session with {expected_links} participants.\n"
        f"Create one manually at {normalize_url(base_url, 'sessions')} and rerun."
    )


# ---------------------------------------------------------------------------
# Page label resolution
# ---------------------------------------------------------------------------
def safe_page_label(url):
    # oTree URLs: /p/{code}/{app}/{PageName}/{round}/  -> PageName is parts[-2]
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[-2] if len(parts) >= 2 else "page"


def resolve_page_label(page):
    """Prefer DOM signatures for the pages that share a template family;
    otherwise fall back to the URL page name (already reliable in oTree)."""
    label = safe_page_label(page.url)
    # Belief vs choice task pages share the round slot but differ by fields:
    if page.locator("input[name='PredictionA']").count() > 0:
        return "Task_ReturnPrediction"
    if page.locator("input[name='AssetToSell'], input[name='AssetToBuy']").count() > 0:
        return "Task_InvestmentDecision"
    if page.locator("input[name='question_1']").count() > 0:
        return "ComprehensionTestPage"
    if page.locator("#nextMonthBtn").count() > 0:
        return "AssetsPerformance"
    return label


# ---------------------------------------------------------------------------
# Generic field filling (text / number / select / radio)
# ---------------------------------------------------------------------------
def fill_fields(page, radio_values):
    # Textareas
    for ta in page.locator("textarea[name]").all():
        name = ta.get_attribute("name")
        if not name:
            continue
        try:
            if not ta.is_visible():
                continue
        except Exception:
            continue
        ta.fill(TEXT_VALUES.get(name, "test response"))

    # Selects
    for sel_el in page.locator("select[name]").all():
        name = sel_el.get_attribute("name")
        if not name:
            continue
        value = radio_values.get(name)
        try:
            if value is not None:
                sel_el.select_option(value=value)
            else:
                opts = sel_el.locator("option").all()
                for opt in opts:
                    v = opt.get_attribute("value")
                    if v:
                        sel_el.select_option(value=v)
                        break
        except Exception:
            pass

    # Text / number inputs (skip hidden, radio, checkbox, submit)
    for inp in page.locator(
        "input[name]:not([type='radio']):not([type='checkbox'])"
        ":not([type='hidden']):not([type='submit'])"
    ).all():
        name = inp.get_attribute("name")
        if not name:
            continue
        try:
            if not inp.is_visible():
                continue
        except Exception:
            continue
        itype = (inp.get_attribute("type") or "text").lower()
        if itype in {"number", "range"}:
            value = NUMBER_VALUES.get(name, "5")
        else:
            value = TEXT_VALUES.get(name, NUMBER_VALUES.get(name, "test"))
        try:
            inp.fill(str(value))
        except Exception:
            pass

    # Radios
    radio_names = page.eval_on_selector_all(
        "input[type='radio'][name]",
        "els => [...new Set(els.map(e => e.name))]",
    )
    for name in radio_names:
        preferred = radio_values.get(name)
        selector = None
        if preferred is not None:
            cand = f"input[type='radio'][name='{name}'][value='{preferred}']"
            if page.locator(cand).count() > 0:
                selector = cand
        if selector is None:
            selector = f"input[type='radio'][name='{name}']"
        loc = page.locator(selector).first
        if loc.count() > 0:
            try:
                loc.check(force=True)
            except Exception:
                loc.evaluate(
                    "el => { el.checked = true;"
                    " el.dispatchEvent(new Event('change', {bubbles:true})); }"
                )


# ---------------------------------------------------------------------------
# Custom page handlers (the JS-gated pages)
# ---------------------------------------------------------------------------
def handle_assets_performance(page):
    """Click through all 12 months to reveal #finalNextBtn, then submit.
    Returns True if it advanced the page."""
    url_before = page.url
    # Click "Next month" until the final submit button appears (max 12 safety).
    for _ in range(12):
        final_btn = page.locator("#finalNextBtn")
        if final_btn.count() > 0 and final_btn.is_visible():
            break
        nxt = page.locator("#nextMonthBtn")
        if nxt.count() == 0 or not nxt.is_visible():
            break
        try:
            nxt.click()
            page.wait_for_timeout(120)
        except Exception:
            break
    # Submit
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
            page.locator("#finalNextBtn").click()
        return True
    except PlaywrightTimeoutError:
        return force_advance_form(page) and page.url != url_before


def handle_return_prediction(page):
    """Fill PredictionA and drive the two hidden-input sliders so the page's
    own validation (sliderTouched) passes, then submit."""
    try:
        page.fill("#PredictionA", NUMBER_VALUES["PredictionA"])
    except Exception:
        pass
    # RiskA and Confidence: set visual range + hidden input + touched flags via JS.
    page.evaluate(
        """
        (val) => {
            ['RiskA', 'Confidence'].forEach(function (name) {
                var visual = document.getElementById(name + '-visual');
                var hidden = document.getElementById(name);
                if (visual) {
                    visual.value = val;
                    visual.classList.add('touched');
                    visual.dispatchEvent(new Event('input', {bubbles: true}));
                }
                if (hidden) { hidden.value = val; }
            });
            if (typeof sliderTouched === 'object') {
                sliderTouched.RiskA = true;
                sliderTouched.Confidence = true;
            }
        }
        """,
        7,
    )
    url_before = page.url
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
            page.locator("button[type='submit'], button.next-btn").first.click()
        return True
    except PlaywrightTimeoutError:
        return force_advance_form(page) and page.url != url_before


def handle_comprehension(page, treatment):
    """Select the correct answers for this treatment, then submit
    (the page's JS only lets you proceed when all four are correct)."""
    key = COMPREHENSION_KEYS.get(treatment)
    if key:
        for i, ans in enumerate(key, start=1):
            sel = f"input[type='radio'][name='question_{i}'][value='{ans}']"
            loc = page.locator(sel).first
            if loc.count() > 0:
                try:
                    loc.check(force=True)
                except Exception:
                    loc.evaluate(
                        "el => { el.checked = true;"
                        " el.dispatchEvent(new Event('change', {bubbles:true})); }"
                    )
    url_before = page.url
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
            page.locator("#submitBtn, button[type='submit']").first.click()
        return True
    except PlaywrightTimeoutError:
        return page.url != url_before


def handle_bot_screening(page):
    """BotScreening.html gates on a Google reCAPTCHA whose data-callback
    ('enableBtn') un-hides the otree Next button (display:none -> block).
    No hidden token field or server check, so we just invoke the callback
    (or force-show the button) and click it."""
    page.evaluate(
        """
        () => {
            // Preferred: call the page's own callback that reveals the button.
            if (typeof enableBtn === 'function') { enableBtn(); }
            // Fallback: force-show the Next button directly.
            const btn = document.querySelector('.otree-btn-next');
            if (btn) {
                btn.style.display = 'block';
                btn.disabled = false;
            }
        }
        """
    )
    page.wait_for_timeout(700)  # enableBtn uses a 500ms setTimeout before showing
    url_before = page.url
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
            page.locator(".otree-btn-next").first.click()
        return True
    except PlaywrightTimeoutError:
        return force_advance_form(page) and page.url != url_before


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------
def next_button_locator(page):
    for selector in [
        "button.otree-btn-next",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Next')",
        "button:has-text('Continue')",
    ]:
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc.first
    return None


def force_advance_form(page):
    try:
        page.evaluate(
            """
            () => {
                const form = document.querySelector('form');
                if (form) { form.submit(); return true; }
                const btn = document.querySelector(
                    'button.otree-btn-next, button[type="submit"], input[type="submit"]');
                if (btn) { btn.click(); return true; }
                return false;
            }
            """
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------
def capture_page(page, target):
    for selector in ["div.otree-body", ".the-whole-space", "main", "form",
                     "div.container", "body"]:
        loc = page.locator(selector).first
        if loc.count() > 0:
            try:
                loc.screenshot(path=str(target))
                return
            except Exception:
                pass
    page.screenshot(path=str(target), full_page=False)


# ---------------------------------------------------------------------------
# Per-participant runner
# ---------------------------------------------------------------------------
def run_participant(page, participant_url, out_dir, folder_label, treatment,
                    max_steps, capture_once_labels, already_captured_once):
    page.goto(participant_url, wait_until="domcontentloaded")
    seen_labels = set()

    # Per-treatment comprehension answers layered onto the base radio table.
    radio_values = dict(RADIO_VALUES)
    key = COMPREHENSION_KEYS.get(treatment)
    if key:
        for i, ans in enumerate(key, start=1):
            radio_values[f"question_{i}"] = str(ans)

    for step in range(1, max_steps + 1):
        page.wait_for_load_state("domcontentloaded")
        plabel = resolve_page_label(page)

        # Screenshot once per label (per treatment; some labels once globally)
        if plabel not in seen_labels:
            should_capture = not (plabel in capture_once_labels
                                  and plabel in already_captured_once)
            if should_capture:
                fname = f"{len(seen_labels) + 1:03d}_{plabel}.png"
                target = out_dir / folder_label / fname
                target.parent.mkdir(parents=True, exist_ok=True)
                capture_page(page, target)
                if plabel in capture_once_labels:
                    already_captured_once.add(plabel)
            seen_labels.add(plabel)


        # --- Testing mode: use the page's own "Skip for testing" button ---
        skip = page.locator("#skipBtn, button:has-text('Skip for testing')").first
        if skip.count() > 0 and skip.is_visible():
            url_before = page.url
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=8000):
                    skip.click()
                continue
            except PlaywrightTimeoutError:
                pass  # fall through to manual handlers below

        # --- Custom JS pages ---
        if plabel == "AssetsPerformance":
            if handle_assets_performance(page):
                continue
        if plabel == "Task_ReturnPrediction":
            if handle_return_prediction(page):
                continue
        if plabel == "ComprehensionTestPage":
            if handle_comprehension(page, treatment):
                continue
        if plabel == "BotScreening":
            if handle_bot_screening(page):
                continue

        # --- Normal pages ---
        btn = next_button_locator(page)
        if btn is None:
            break
        fill_fields(page, radio_values)

        url_before = page.url
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=6000):
                btn.click()
        except PlaywrightTimeoutError:
            if page.url == url_before and not force_advance_form(page):
                break

        if "LinkToProlific" in page.url:
            page.wait_for_load_state("domcontentloaded")
            end_label = resolve_page_label(page)
            target = out_dir / folder_label / f"{len(seen_labels) + 1:03d}_{end_label}.png"
            if end_label not in seen_labels:
                capture_page(page, target)
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url",  default=BASE_URL)
    parser.add_argument("--config",    default=SESSION_CONFIG_NAME)
    parser.add_argument("--treatments", type=int, default=NUM_TREATMENTS)
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument("--out",       default=OUT_DIR)
    parser.add_argument("--testing",   action="store_true", default=TESTING_MODE)
    parser.add_argument("--no-testing", dest="testing", action="store_false")
    parser.add_argument("--headed",    action="store_true", default=HEADED)
    parser.add_argument("--no-headed", dest="headed", action="store_false")
    args = parser.parse_args()

    num_treatments = args.treatments
    out_dir = Path(args.out) / f"{APP_NAME}"
    out_dir.mkdir(parents=True, exist_ok=True)
    already_captured_once = set()

    print(f"\n{'='*60}")
    print(f"  ME Screenshot Capture")
    print(f"  Config     : {args.config}   (testing={args.testing})")
    print(f"  Treatments : {num_treatments}  |  Headed: {args.headed}")
    print(f"  Output     : {out_dir.resolve()}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        setup_page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=2)

        print(f"Creating session with {num_treatments} participant slots...")
        links = create_session_and_get_links(
            page=setup_page, base_url=args.base_url,
            config_name=args.config, expected_links=num_treatments,
            testing=args.testing,
        )
        setup_page.close()

        for t_idx in range(num_treatments):
            if t_idx >= len(links):
                print(f"  Warning: ran out of links at treatment {t_idx + 1}")
                break
            treatment = t_idx + 1  # id_in_session order -> treatment (mod 16)+1
            folder = f"treatment_{treatment:02d}_{treatment_label(treatment)}"
            print(f"  [{treatment:02d}/{num_treatments}] {treatment_label(treatment)}")

            run_page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=2)
            run_participant(
                page=run_page,
                participant_url=links[t_idx],
                out_dir=out_dir,
                folder_label=folder,
                treatment=treatment,
                max_steps=args.max_steps,
                capture_once_labels=CAPTURE_ONCE_LABELS,
                already_captured_once=already_captured_once,
            )
            run_page.close()

        browser.close()

    print(f"\nDone. Screenshots saved to: {out_dir.resolve()}")
    print("Next:  review, then  otree resetdb")


if __name__ == "__main__":
    main()
