"""
Browser Tools — Web search, site-targeted search, and browser interaction tools.

Provides:
  - search_web()        : General DuckDuckGo search (no API key, always available)
  - search_site()       : Platform-specific targeted search (YouTube, Google, Reddit, GitHub, etc.)
  - navigate_to()       : Open URL in default or specified browser (Edge, Chrome, Brave, etc.)
  - open_url()          : Direct URL opener with optional browser targeting
  - web_search_tavily() : Tavily API (requires TAVILY_API_KEY, higher quality)
"""
from __future__ import annotations

import os
import subprocess
import urllib.parse
import webbrowser
from typing import Any

from langchain_core.tools import tool as lc_tool

# Ordered list so tool schema registration is deterministic
TOOLS = [
    "search_web",
    "search_site",
    "navigate_to",
    "open_url",
    "fill_form",
    "click_web_element",
    "get_page_text",
    "download_file",
    "take_page_screenshot",
    "scroll_page",
]

# ── Supported Web Platforms and Search URL Templates ──────────────────────────

WEB_PLATFORMS: dict[str, dict[str, str]] = {
    "youtube": {
        "name": "YouTube",
        "base": "https://www.youtube.com",
        "search": "https://www.youtube.com/results?search_query={q}",
    },
    "yt": {
        "name": "YouTube",
        "base": "https://www.youtube.com",
        "search": "https://www.youtube.com/results?search_query={q}",
    },
    "google": {
        "name": "Google",
        "base": "https://www.google.com",
        "search": "https://www.google.com/search?q={q}",
    },
    "github": {
        "name": "GitHub",
        "base": "https://github.com",
        "search": "https://github.com/search?q={q}",
    },
    "reddit": {
        "name": "Reddit",
        "base": "https://www.reddit.com",
        "search": "https://www.reddit.com/search/?q={q}",
    },
    "amazon": {
        "name": "Amazon",
        "base": "https://www.amazon.com",
        "search": "https://www.amazon.com/s?k={q}",
    },
    "wikipedia": {
        "name": "Wikipedia",
        "base": "https://en.wikipedia.org",
        "search": "https://en.wikipedia.org/w/index.php?search={q}",
    },
    "wiki": {
        "name": "Wikipedia",
        "base": "https://en.wikipedia.org",
        "search": "https://en.wikipedia.org/w/index.php?search={q}",
    },
    "twitter": {
        "name": "Twitter / X",
        "base": "https://x.com",
        "search": "https://x.com/search?q={q}",
    },
    "x": {
        "name": "X",
        "base": "https://x.com",
        "search": "https://x.com/search?q={q}",
    },
    "spotify": {
        "name": "Spotify",
        "base": "https://open.spotify.com",
        "search": "https://open.spotify.com/search/{q}",
    },
    "netflix": {
        "name": "Netflix",
        "base": "https://www.netflix.com",
        "search": "https://www.netflix.com/search?q={q}",
    },
    "chatgpt": {
        "name": "ChatGPT",
        "base": "https://chatgpt.com",
        "search": "https://chatgpt.com",
    },
    "claude": {
        "name": "Claude",
        "base": "https://claude.ai",
        "search": "https://claude.ai",
    },
    "gmail": {
        "name": "Gmail",
        "base": "https://mail.google.com",
        "search": "https://mail.google.com/mail/u/0/#search/{q}",
    },
    "maps": {
        "name": "Google Maps",
        "base": "https://maps.google.com",
        "search": "https://www.google.com/maps/search/{q}",
    },
    "google maps": {
        "name": "Google Maps",
        "base": "https://maps.google.com",
        "search": "https://www.google.com/maps/search/{q}",
    },
    "stackoverflow": {
        "name": "Stack Overflow",
        "base": "https://stackoverflow.com",
        "search": "https://stackoverflow.com/search?q={q}",
    },
    "stack overflow": {
        "name": "Stack Overflow",
        "base": "https://stackoverflow.com",
        "search": "https://stackoverflow.com/search?q={q}",
    },
    "instagram": {
        "name": "Instagram",
        "base": "https://www.instagram.com",
        "search": "https://www.instagram.com/explore/tags/{q}",
    },
    "facebook": {
        "name": "Facebook",
        "base": "https://www.facebook.com",
        "search": "https://www.facebook.com/search/top?q={q}",
    },
    "linkedin": {
        "name": "LinkedIn",
        "base": "https://www.linkedin.com",
        "search": "https://www.linkedin.com/search/results/all/?keywords={q}",
    },
    "twitch": {
        "name": "Twitch",
        "base": "https://www.twitch.tv",
        "search": "https://www.twitch.tv/search?term={q}",
    },
    "pinterest": {
        "name": "Pinterest",
        "base": "https://www.pinterest.com",
        "search": "https://www.pinterest.com/search/pins/?q={q}",
    },
    "bing": {
        "name": "Bing",
        "base": "https://www.bing.com",
        "search": "https://www.bing.com/search?q={q}",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "base": "https://duckduckgo.com",
        "search": "https://duckduckgo.com/?q={q}",
    },
    "ddg": {
        "name": "DuckDuckGo",
        "base": "https://duckduckgo.com",
        "search": "https://duckduckgo.com/?q={q}",
    },
    "yahoo": {
        "name": "Yahoo",
        "base": "https://search.yahoo.com",
        "search": "https://search.yahoo.com/search?p={q}",
    },
    "huggingface": {
        "name": "Hugging Face",
        "base": "https://huggingface.co",
        "search": "https://huggingface.co/models?search={q}",
    },
    "arxiv": {
        "name": "arXiv",
        "base": "https://arxiv.org",
        "search": "https://arxiv.org/search/?query={q}&searchtype=all",
    },
    "imdb": {
        "name": "IMDb",
        "base": "https://www.imdb.com",
        "search": "https://www.imdb.com/find/?q={q}",
    },
    "ebay": {
        "name": "eBay",
        "base": "https://www.ebay.com",
        "search": "https://www.ebay.com/sch/i.html?_nkw={q}",
    },
}

# Browser name mapping to Windows executable / alias
BROWSER_EXE_MAP: dict[str, list[str]] = {
    "edge": ["msedge.exe", "msedge"],
    "ms edge": ["msedge.exe", "msedge"],
    "msedge": ["msedge.exe", "msedge"],
    "microsoft edge": ["msedge.exe", "msedge"],
    "chrome": ["chrome.exe", "chrome"],
    "google chrome": ["chrome.exe", "chrome"],
    "google": ["chrome.exe", "chrome"],
    "brave": ["brave.exe", "brave"],
    "brave browser": ["brave.exe", "brave"],
    "firefox": ["firefox.exe", "firefox"],
    "mozilla": ["firefox.exe", "firefox"],
    "mozilla firefox": ["firefox.exe", "firefox"],
    "opera": ["opera.exe", "opera"],
}


def _launch_url_in_browser(url: str, browser: str = "") -> bool:
    """Launch a URL inside a specific browser or fallback to system default."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    clean_browser = browser.lower().strip() if browser else ""
    detached_flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )

    if clean_browser and clean_browser in BROWSER_EXE_MAP:
        exes = BROWSER_EXE_MAP[clean_browser]
        # 1. Try resolving via find_windows_app
        try:
            from woody.tools.builtin.desktop_tools import find_windows_app
            for exe_cand in exes:
                resolved = find_windows_app(exe_cand)
                if resolved and os.path.exists(resolved):
                    subprocess.Popen([resolved, url], shell=False, close_fds=True, creationflags=detached_flags)
                    return True
        except Exception:
            pass

        # 2. Try direct command execution
        for exe_cand in exes:
            try:
                subprocess.Popen([exe_cand, url], shell=False, close_fds=True, creationflags=detached_flags)
                return True
            except Exception:
                pass

        # 3. Try start with browser command
        try:
            primary_exe = exes[0]
            subprocess.Popen(f'start "" "{primary_exe}" "{url}"', shell=True, close_fds=True)
            return True
        except Exception:
            pass

    # Fallback: System default browser
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


# ── Search Site / Platform Tool ───────────────────────────────────────────────

def search_site(query: str, site: str = "youtube", browser: str = "") -> dict:
    """Search for a specific query directly on a website or platform (e.g. YouTube, Google, Reddit, GitHub, Amazon).

    Args:
        query: The search term or topic (e.g. 'iphone', 'lofi beats', 'python tutorial').
        site: The target platform or website name (e.g. 'youtube', 'google', 'reddit', 'github', 'amazon', 'spotify').
        browser: Optional specific browser to use (e.g. 'edge', 'chrome', 'brave', 'firefox').
    """
    clean_site = site.lower().strip()
    clean_query = query.strip()
    encoded_query = urllib.parse.quote_plus(clean_query)

    platform_info = WEB_PLATFORMS.get(clean_site)
    if platform_info and "search" in platform_info:
        search_url = platform_info["search"].format(q=encoded_query)
        site_name = platform_info.get("name", clean_site.capitalize())
    else:
        # Fallback to Google site search if unknown platform
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(f'{clean_query} on {clean_site}')}"
        site_name = clean_site.capitalize()

    browser_label = f" on {browser}" if browser else ""
    success = _launch_url_in_browser(search_url, browser=browser)

    if success:
        return {
            "success": True,
            "query": clean_query,
            "site": site_name,
            "browser": browser or "default",
            "url": search_url,
            "message": f"Searched '{clean_query}' on {site_name}{browser_label}.",
        }
    return {
        "success": False,
        "error": f"Failed to open {site_name} search for '{clean_query}'.",
    }


def open_url(url: str, browser: str = "") -> dict:
    """Open any URL in a web browser, with optional browser specification (Edge, Chrome, Brave, Firefox).

    Args:
        url: The web URL or domain to open (e.g. 'https://youtube.com', 'github.com', 'reddit.com').
        browser: Optional specific browser to use (e.g. 'edge', 'chrome', 'brave', 'firefox').
    """
    if not url:
        return {"success": False, "error": "No URL provided."}

    # Normalize platform shortcuts like 'youtube' -> 'https://www.youtube.com'
    url_lower = url.lower().strip()
    if url_lower in WEB_PLATFORMS:
        url = WEB_PLATFORMS[url_lower]["base"]

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    browser_label = f" on {browser}" if browser else ""
    success = _launch_url_in_browser(url, browser=browser)
    if success:
        return {
            "success": True,
            "url": url,
            "browser": browser or "default",
            "message": f"Opened {url}{browser_label}.",
        }
    return {"success": False, "error": f"Could not open URL: {url}"}


def navigate_to(url: str, browser: str = "") -> dict:
    """Open a URL or website in the default or specified web browser.

    Args:
        url: The URL or website name to open (e.g. 'https://youtube.com', 'google.com', 'youtube').
        browser: Optional browser name (e.g. 'edge', 'chrome', 'brave', 'firefox').
    """
    return open_url(url=url, browser=browser)


# ── Tavily Web Search ─────────────────────────────────────────────────────────

@lc_tool
def web_search_tavily(query: str) -> str:
    """Search the web using Tavily API and return formatted results.
    Requires TAVILY_API_KEY environment variable.

    Args:
        query: The search query string.
    """
    try:
        from langchain_tavily import TavilySearch  # type: ignore
        tavily = TavilySearch(max_results=4)
        res = tavily.invoke(query)
        if isinstance(res, dict) and "results" in res:
            formatted = []
            for item in res["results"]:
                snippet = item.get("content", "")[:350]
                formatted.append(
                    f"**{item.get('title', '')}**\n"
                    f"URL: {item.get('url', '')}\n"
                    f"{snippet}"
                )
            return "\n\n".join(formatted) or "No results found."
        return str(res)[:1500]
    except ImportError:
        return "Tavily not installed. Run: pip install langchain-tavily"
    except Exception as e:
        return f"Tavily search error: {e}"


# ── DuckDuckGo Search (@tool for LangGraph) ────────────────────────────────────

@lc_tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (no API key required).
    Returns a formatted string of result snippets.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).
    """
    result = search_web_duckduckgo(query=query, max_results=max_results)
    if result.get("success"):
        return "\n\n".join(result.get("results", ["No results found."]))
    return f"Search error: {result.get('error', 'Unknown error')}"


def search_web_duckduckgo(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo and return a list of result snippets.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).
    """
    try:
        import httpx

        # URL-encode the query to handle spaces and special characters correctly
        encoded_query = urllib.parse.quote_plus(query)

        # Use the DDG JSON (Instant Answer) API — no JS, no HTML parsing fragility
        json_url = (
            f"https://api.duckduckgo.com/?q={encoded_query}"
            f"&format=json&no_html=1&skip_disambig=1"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }

        resp = httpx.get(json_url, headers=headers, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

        results: list[str] = []

        # 1. Abstract (best single answer)
        abstract = data.get("Abstract", "").strip()
        if abstract:
            source = data.get("AbstractSource", "")
            url = data.get("AbstractURL", "")
            results.append(f"{abstract} — {source} ({url})" if source else abstract)

        # 2. Related topics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if isinstance(topic, dict):
                text = topic.get("Text", "").strip()
                if text:
                    results.append(text)

        # 3. Fallback: HTML search if the JSON API returned nothing useful
        if not results:
            html_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            html_resp = httpx.get(
                html_url, headers=headers, timeout=10.0, follow_redirects=True
            )
            html_resp.raise_for_status()
            import re
            snippets = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>',
                html_resp.text,
                re.DOTALL,
            )
            clean = re.compile(r"<[^>]+>")
            for s in snippets[:max_results]:
                text = clean.sub("", s).strip()
                if text:
                    results.append(text)

        if not results:
            return {"success": True, "results": ["No results found for the given query."]}

        return {"success": True, "query": query, "results": results[:max_results]}

    except Exception as e:
        return {"success": False, "error": str(e)}


def fill_form(selector: str, value: str) -> dict:
    """Fill a web form field identified by a CSS selector. [Phase 3 — Playwright]

    Args:
        selector: CSS selector for the input element.
        value: Text to type into the field.
    """
    return {"success": False, "error": "fill_form requires Phase 3 Playwright integration."}


def click_web_element(selector: str) -> dict:
    """Click a web element identified by a CSS selector or visible text. [Phase 3 — Playwright]

    Args:
        selector: CSS selector or visible text of the element to click.
    """
    return {"success": False, "error": "click_web_element requires Phase 3 Playwright integration."}


def get_page_text() -> dict:
    """Get the visible text content of the currently active browser page. [Phase 3 — Playwright]"""
    return {"success": False, "error": "get_page_text requires Phase 3 Playwright integration."}


def download_file(url: str, destination: str = "") -> dict:
    """Download a file from a URL to a local path. [Phase 3 — Playwright]

    Args:
        url: The URL of the file to download.
        destination: Local path where the file should be saved.
    """
    return {"success": False, "error": "download_file requires Phase 3 Playwright integration."}


def take_page_screenshot() -> dict:
    """Capture a screenshot of the currently active browser page. [Phase 3 — Playwright]"""
    return {"success": False, "error": "take_page_screenshot requires Phase 3 Playwright integration."}


def scroll_page(direction: str = "down", amount: int = 3) -> dict:
    """Scroll the currently active browser page.

    Args:
        direction: Scroll direction — 'up' or 'down'.
        amount: Number of page-heights to scroll.
    """
    return {"success": False, "error": "scroll_page requires Phase 3 Playwright integration."}
