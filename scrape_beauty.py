import asyncio
import re
from urllib.parse import unquote
from playwright.async_api import async_playwright
import pandas as pd

# ── STEP 1: Scroll and collect all Maps links ────────────────────────────────

async def collect_business_links(page, search_url, max_scrolls=30):
    print(f"\n🔍 Searching: {search_url}")
    await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(5000)

    all_links = set()
    no_new_streak = 0

    for i in range(max_scrolls):
        await page.evaluate("""
            const feed = document.querySelector('div[role="feed"]');
            if (feed) feed.scrollBy(0, 1000);
        """)
        await page.wait_for_timeout(2000)

        html = await page.content()
        links = re.findall(r'href="(https://www\.google\.com/maps/place/[^"]+)"', html)

        before = len(all_links)
        for link in links:
            all_links.add(link.replace("&amp;", "&"))
        after = len(all_links)

        print(f"  Scroll {i+1}/{max_scrolls} → {after} businesses found")

        if after == before:
            no_new_streak += 1
            if no_new_streak >= 3:
                print("  No new results, stopping.")
                break
        else:
            no_new_streak = 0

    return list(all_links)


# ── STEP 2: Visit each Maps page, click through to get real website ──────────

async def extract_maps_details(page, url):
    name, phone, website = "", "", ""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        # Business name from h1
        try:
            name = await page.inner_text("h1", timeout=3000)
            name = name.strip()
        except:
            pass

        # Phone — look for aria-label containing phone number
        try:
            phone_el = await page.query_selector('[data-tooltip="Copy phone number"]')
            if phone_el:
                phone = await phone_el.get_attribute("aria-label")
                phone = phone.replace("Phone:", "").strip() if phone else ""
        except:
            pass

        # If phone still empty, try text matching
        if not phone:
            try:
                html = await page.content()
                phone_match = re.search(r'(\+?8801[3-9]\d{8}|01[3-9]\d{8})', html)
                if phone_match:
                    phone = phone_match.group(0)
            except:
                pass

        # Website — find the actual website button/link on the Maps page
        try:
            # Google Maps shows website as a link with the actual URL
            website_el = await page.query_selector('a[data-tooltip="Open website"]')
            if website_el:
                website = await website_el.get_attribute("href")
            
            # Fallback: look for website link in page
            if not website:
                html = await page.content()
                # Match only proper business websites, exclude all Google domains
                matches = re.findall(
                    r'href="(https?://(?!(?:[a-z]+\.)?google\.|goo\.gl|maps\.app|fonts\.|gstatic\.|googleapis\.)[^"]{5,})"',
                    html
                )
                # Filter out obviously wrong URLs
                blacklist = ["google", "gstatic", "googleapis", "facebook.com/sharer",
                            "twitter.com/intent", "support.", "policies", "schema.org",
                            "w3.org", "apple.com", "microsoft.com"]
                for m in matches:
                    if not any(b in m for b in blacklist):
                        website = m
                        break
        except:
            pass

    except Exception as e:
        print(f"    ⚠ Maps detail failed: {e}")

    return name, phone, website


# ── STEP 3: Visit website and extract email + socials ────────────────────────

async def extract_website_contacts(page, url):
    email, facebook, instagram = "", "", ""
    if not url:
        return email, facebook, instagram

    base = url.rstrip("/")
    pages_to_try = [base, base + "/contact", base + "/contact-us", base + "/about"]

    for try_url in pages_to_try:
        try:
            await page.goto(try_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            html = await page.content()

            # Email
            emails = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w{2,}', html)
            bad = ["example", "domain", "sentry", "schema", "wix", "jquery",
                   "png", "jpg", "svg", "apache", "wordpress", "email"]
            emails = [e for e in emails if not any(b in e.lower() for b in bad)]
            if emails:
                email = emails[0]

            # Facebook
            fb = re.search(r'https?://(?:www\.)?facebook\.com/([\w\.]+)', html)
            if fb and fb.group(1) not in ["sharer", "share", "dialog"]:
                facebook = "https://facebook.com/" + fb.group(1)

            # Instagram
            ig = re.search(r'https?://(?:www\.)?instagram\.com/([\w\.]+)', html)
            if ig and ig.group(1) not in ["p", "share"]:
                instagram = "https://instagram.com/" + ig.group(1)

            if email:  # Got email, no need to check more pages
                break

        except:
            continue

    return email, facebook, instagram


# ── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    # Only beauty/aesthetics keywords — removed laser/dental ones
    keywords = [
        "beauty salon Dhaka",
        "beauty parlour Dhaka",
        "skincare clinic Dhaka",
        "spa wellness center Dhaka",
        "aesthetic clinic Dhaka",
        "beauty salon Gulshan",
        "beauty salon Dhanmondi",
        "beauty salon Banani",
        "beauty salon Uttara",
        "beauty salon Mirpur",
        "makeup studio Dhaka",
        "nail salon Dhaka",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Step 1 — collect all Maps links
        all_links = set()
        for keyword in keywords:
            url = f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}/"
            links = await collect_business_links(page, url, max_scrolls=30)
            all_links.update(links)

        print(f"\n✅ Total unique businesses: {len(all_links)}")

        # Step 2 & 3 — extract details
        results = []
        for i, maps_url in enumerate(all_links):
            print(f"\n[{i+1}/{len(all_links)}] Extracting...")

            name, phone, website = await extract_maps_details(page, maps_url)
            print(f"  📌 {name} | 📞 {phone} | 🌐 {website}")

            email, facebook, instagram = await extract_website_contacts(page, website)
            print(f"  📧 {email} | FB: {facebook} | IG: {instagram}")

            results.append({
                "Business Name": name,
                "Phone": phone,
                "Website": website,
                "Email": email,
                "Facebook": facebook,
                "Instagram": instagram,
                "Google Maps URL": maps_url,
            })

            # Save progress every 10
            if (i + 1) % 10 == 0:
                df = pd.DataFrame(results)
                df.to_excel("beauty_dhaka_progress.xlsx", index=False)
                print(f"  💾 Progress saved ({i+1} done)")

        await browser.close()

    # Final save
    df = pd.DataFrame(results)
    df.drop_duplicates(subset="Business Name", inplace=True)
    df.to_excel("beauty_dhaka_FINAL.xlsx", index=False)
    print(f"\n🎉 Done! {len(df)} businesses → beauty_dhaka_FINAL.xlsx")

asyncio.run(main())