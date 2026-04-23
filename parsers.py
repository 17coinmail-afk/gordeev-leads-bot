import asyncio
import re
from typing import List, Dict

import aiohttp
import feedparser
from bs4 import BeautifulSoup
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

RSS_URLS = {
    "fl": "https://www.fl.ru/rss/all.xml",
}


async def fetch_rss(session: aiohttp.ClientSession, name: str, url: str):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), headers=HEADERS) as resp:
            text = await resp.text()
            return name, text
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return name, None


def parse_budget(text: str) -> str:
    text = text.replace("\xa0", " ")
    patterns = [
        r"\b\d[\d\s]*\s*(?:руб|₽|RUB|rub)\.?\b",
        r"\b\d[\d\s]*\s*(?:usd|\$|доллар)\.?\b",
        r"\b\d[\d\s]*\s*(?:евро|€|euro)\.?\b",
        r"бюджет[:\s]+(\d[\d\s]*)",
        r"оплата[:\s]+(\d[\d\s]*)",
        r"\d{3,}\s*[-–]\s*\d{3,}",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return "Не указан"


def parse_feed(name: str, xml_text: str) -> List[Dict]:
    feed = feedparser.parse(xml_text)
    projects = []
    for entry in feed.entries:
        title = entry.get("title", "")
        description = entry.get("summary", entry.get("description", ""))
        link = entry.get("link", "")
        published = entry.get("published", "")
        full_text = f"{title} {description}"
        budget = parse_budget(full_text)
        projects.append(
            {
                "source": name,
                "title": title,
                "description": description,
                "link": link,
                "published_at": published,
                "budget": budget,
            }
        )
    return projects


async def parse_freelance_ru(session: aiohttp.ClientSession) -> List[Dict]:
    url = "https://freelance.ru/projects"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), headers=HEADERS) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            projects = []
            cards = soup.find_all("div", class_=lambda x: x and "project-item-default-card" in x)
            for card in cards:
                title_a = card.select_one("h2.title a")
                if not title_a:
                    continue
                title = title_a.get_text(strip=True)
                href = title_a.get("href", "")
                if href.startswith("/"):
                    href = f"https://freelance.ru{href}"
                
                desc_a = card.select_one("a.description")
                description = desc_a.get_text(strip=True) if desc_a else ""
                
                cost_div = card.select_one("div.cost")
                budget = cost_div.get_text(strip=True) if cost_div else "Не указан"
                
                projects.append(
                    {
                        "source": "freelance_ru",
                        "title": title,
                        "description": description,
                        "link": href,
                        "published_at": "",
                        "budget": budget,
                    }
                )
            return projects
    except Exception as e:
        print(f"Error parsing freelance.ru: {e}")
        return []


async def parse_kwork() -> List[Dict]:
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not available, skipping Kwork")
        return []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Скрываем headless
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            await page.goto("https://kwork.ru/projects?category=all", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            cards = await page.query_selector_all(".want-card")
            projects = []
            for card in cards:
                title_el = await card.query_selector(".wants-card__header-title a")
                if not title_el:
                    continue
                title = await title_el.inner_text()
                href = await title_el.get_attribute("href") or ""
                if href.startswith("/"):
                    href = f"https://kwork.ru{href}"

                desc_el = await card.query_selector(".wants-card__description-text")
                description = await desc_el.inner_text() if desc_el else ""

                price_el = await card.query_selector(".wants-card__price")
                price = await price_el.inner_text() if price_el else "Не указан"

                projects.append(
                    {
                        "source": "kwork",
                        "title": title,
                        "description": description,
                        "link": href,
                        "published_at": "",
                        "budget": price,
                    }
                )
            await browser.close()
            print(f"Parsed {len(projects)} projects from kwork (Playwright)")
            return projects
    except Exception as e:
        print(f"Error parsing kwork with Playwright: {e}")
        return []


async def fetch_all_projects() -> List[Dict]:
    all_projects = []

    # RSS + простой HTML
    async with aiohttp.ClientSession() as session:
        rss_tasks = [fetch_rss(session, name, url) for name, url in RSS_URLS.items()]
        rss_results = await asyncio.gather(*rss_tasks)

        for name, xml_text in rss_results:
            if xml_text:
                try:
                    projects = parse_feed(name, xml_text)
                    all_projects.extend(projects)
                    print(f"Parsed {len(projects)} projects from {name} (RSS)")
                except Exception as e:
                    print(f"Error parsing RSS {name}: {e}")

        # HTML-источник без JS
        freelance_projects = await parse_freelance_ru(session)
        if freelance_projects:
            all_projects.extend(freelance_projects)

    # JS-источники (Playwright)
    kwork_projects = await parse_kwork()
    if kwork_projects:
        all_projects.extend(kwork_projects)

    return all_projects
