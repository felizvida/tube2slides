from __future__ import annotations


SUPPORTED_COOKIE_BROWSERS = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
}


def normalize_cookie_browser(value: str | None) -> str | None:
    browser = (value or "").strip().lower()
    if not browser:
        return None
    if browser not in SUPPORTED_COOKIE_BROWSERS:
        supported = ", ".join(sorted(SUPPORTED_COOKIE_BROWSERS))
        raise ValueError(f"unsupported browser for cookies: {browser}. Supported browsers: {supported}")
    return browser


def ytdlp_cookie_cli_args(browser: str | None) -> list[str]:
    browser = normalize_cookie_browser(browser)
    if not browser:
        return []
    return ["--cookies-from-browser", browser]


def ytdlp_cookie_options(browser: str | None) -> dict[str, tuple[str, None, None, None]]:
    browser = normalize_cookie_browser(browser)
    if not browser:
        return {}
    return {"cookiesfrombrowser": (browser, None, None, None)}
