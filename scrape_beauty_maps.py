import googlemaps
import pandas as pd
import time
import asyncio
# Paste your API key here
API_KEY = "AIzaSyBXf16DYP2q0xmTPupeAftftbqAQZUKuQs"

gmaps = googlemaps.Client(key=API_KEY)

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def scrape_maps():
    browser_cfg = BrowserConfig(
        headless=False,
        java_script_enabled=True,
    )

    run_cfg = CrawlerRunConfig(
        wait_for="css:div[role='feed']",   # Waits until the business list panel loads
        delay_before_return_html=8.0,       # Extra 8 seconds buffer
        page_timeout=30000,
    )

    search_url = "https://www.google.com/maps/search/beauty+salon+Dhaka/"

    print("Opening browser and going to Google Maps...")

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(
            url=search_url,
            config=run_cfg
        )

        # Save raw output to a file so you can inspect it fully
        with open("output.txt", "w", encoding="utf-8") as f:
            f.write(result.markdown)

        print("Done! Output saved to output.txt")
        print("\nPreview (first 2000 chars):")
        print(result.markdown[:2000])

asyncio.run(scrape_maps())