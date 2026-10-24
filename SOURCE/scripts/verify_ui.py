from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "artifacts/system_tests")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    screenshots = args.output / "screenshots"
    screenshots.mkdir(exist_ok=True)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "scope": "Real Chromium UI and two real backend exchanges; explicit network fault simulation for exception tests.", "checks": []}
    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
        print(name, "PASS", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_default_timeout(12000)
        try:
            page.goto(args.url, wait_until="networkidle", timeout=90000)
            check("welcome_desktop", page.get_by_role("heading", level=1).is_visible())
            page.screenshot(path=str(screenshots / "desktop-welcome.png"), full_page=True)
            field = page.get_by_label("Câu hỏi của bạn")
            check("empty_send_disabled", page.get_by_role("button", name="Gửi câu hỏi", exact=True).is_disabled())
            field.fill("Đơn vị mã 00070 thuộc tỉnh thành nào?")
            page.get_by_role("button", name="Gửi câu hỏi", exact=True).click()
            page.locator(".answer-status").wait_for(timeout=90000)
            check("real_kg_response", "00070" in page.locator(".answer-text").last.inner_text() and "Hà Nội" in page.locator(".answer-text").last.inner_text())
            page.locator(".sources summary").last.click()
            check("real_sources_visible", page.locator(".source-card").count() > 0)
            field.fill("Đơn vị đó thuộc tỉnh nào?")
            field.press("Enter")
            page.locator(".answer-status").nth(1).wait_for(timeout=90000)
            check("real_conversational_context", "00070" in page.locator(".answer-text").last.inner_text())
            check("context_resolution_displayed", page.get_by_text("Đã liên kết ngữ cảnh", exact=True).is_visible())
            page.screenshot(path=str(screenshots / "desktop-answer.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.getElementById('sidebar').getBoundingClientRect().right <= 1")
            check("mobile_navigation_initially_hidden", page.locator("#sidebar").evaluate("el => el.getBoundingClientRect().right <= 1"))
            page.screenshot(path=str(screenshots / "mobile-answer.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_role("button", name="Sao chép", exact=True).last.click()
            page.get_by_role("button", name="Đã sao chép", exact=True).wait_for()
            check("copy_answer", page.get_by_role("button", name="Đã sao chép", exact=True).count() > 0)
            page.reload(wait_until="networkidle")
            check("history_persisted", page.locator(".session").count() == 1)
            page.locator(".session").first.click()
            check("restored_answer", page.locator(".answer-text").count() == 2)
            page.get_by_role("button", name="Cuộc trò chuyện mới").click()
            check("new_chat_keeps_history", page.locator(".answer-text").count() == 0 and page.locator(".session").count() == 1)
            page.locator("#about").click()
            check("scope_dialog", page.locator("#scope-dialog").is_visible())
            page.keyboard.press("Escape")
            check("scope_dialog_closes", not page.locator("#scope-dialog").is_visible())
            requests = []
            page.route("**/v1/chat", lambda route: requests.append(route))
            field.fill("Câu hỏi đang xử lý")
            field.press("Shift+Enter")
            check("shift_enter_newline", "\n" in field.input_value() and len(requests) == 0)
            field.press("Enter")
            page.locator("#pending").wait_for()
            page.wait_for_timeout(200)
            check("pending_prevents_duplicate", page.locator("#send").is_disabled() and len(requests) == 1)
            field.press("Enter")
            page.wait_for_timeout(100)
            check("enter_does_not_duplicate_pending", len(requests) == 1)
            page.locator("#stop").click()
            check("cancel_releases_composer", page.locator("#pending").count() == 0 and page.locator("#stop").is_hidden())
            for route in requests:
                try:
                    route.abort()
                except Exception:
                    pass
            page.unroute("**/v1/chat")
            page.route("**/v1/chat", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"unavailable"}'))
            field.fill("Thử lỗi máy chủ")
            field.press("Enter")
            page.locator(".error-text").last.wait_for()
            check("server_503_is_explained", "chưa sẵn sàng" in page.locator(".error-text").last.inner_text())
            page.get_by_role("button", name="Thử lại câu hỏi").last.click()
            check("retry_restores_question", field.input_value() == "Thử lỗi máy chủ")
            page.unroute("**/v1/chat")
            page.route("**/v1/chat", lambda route: route.fulfill(status=200, content_type="text/html", body="<html>bad gateway</html>"))
            field.press("Enter")
            page.locator(".error-text").nth(1).wait_for()
            check("malformed_json_is_explained", "chưa đọc được" in page.locator(".error-text").last.inner_text())
            page.unroute("**/v1/chat")
            context.set_offline(True)
            field.fill("Thử khi mất mạng")
            field.press("Enter")
            page.locator(".error-text").nth(2).wait_for()
            check("offline_is_explained", "Không kết nối được" in page.locator(".error-text").last.inner_text())
            context.set_offline(False)
            payload = {"status": "answered", "answer": '<img src=x onerror="window.__xss=1"> Hồ Hoàn Kiếm', "citations": [
                {"number": 1, "kind": "rag", "title": '<script>window.__xss=1</script>', "source": "test", "source_url": "javascript:alert(1)"}], "timings_ms": {"total": 10}}
            page.route("**/v1/chat", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)))
            field.fill("Thử hiển thị văn bản an toàn")
            field.press("Enter")
            page.locator(".sources summary").last.wait_for()
            page.locator(".sources summary").last.click()
            check("html_is_text_not_executed", page.evaluate("window.__xss === undefined") and page.locator(".answer-text img").count() == 0)
            check("unsafe_source_link_rejected", page.locator(".source-card a").count() == 0)
            page.unroute("**/v1/chat")
            page.set_viewport_size({"width": 390, "height": 844})
            check("mobile_no_horizontal_overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check("mobile_send_visible", page.locator("#send").is_visible())
            page.locator("#menu").click()
            check("mobile_navigation_opens", page.locator("#sidebar").evaluate("el => el.classList.contains('open')"))
            page.keyboard.press("Escape")
            check("mobile_navigation_closes", page.locator("#menu").get_attribute("aria-expanded") == "false")
            page.wait_for_function("document.getElementById('sidebar').getBoundingClientRect().right <= 1")
            page.screenshot(path=str(screenshots / "mobile-safe-text.png"), full_page=True)
            page.on("dialog", lambda dialog: dialog.accept())
            page.locator("#clear-chat").click()
            check("delete_chat_keeps_other_history", page.locator(".session").count() == 1)
            check("mobile_welcome_starts_at_top", page.locator("#conversation-scroll").evaluate("el => el.scrollTop < 5"))
            page.screenshot(path=str(screenshots / "mobile-welcome.png"), full_page=True)
            check("no_browser_javascript_errors", not errors)
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "message": str(error), "trace": traceback.format_exc()}
            page.screenshot(path=str(screenshots / "failure.png"), full_page=True)
        finally:
            report["browser_errors"] = errors
            report["passed"] = "error" not in report and all(item["passed"] for item in report["checks"])
            report["check_count"] = len(report["checks"])
            (args.output / "ui_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
            browser.close()
    print(json.dumps({"passed": report["passed"], "checks": report["check_count"], "report": str(args.output / "ui_report.json")}), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
