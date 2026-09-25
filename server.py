import re
from urllib.parse import urljoin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TargetRequest(BaseModel):
    target: str


def clean_domain(target: str) -> str:
    target = (
        target.strip()
        .lower()
        .replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
    )
    if "." not in target:
        target = f"{target}.com"
    return target


@app.post("/scrape")
def scrape_emails(req: TargetRequest):
    domain = clean_domain(req.target)
    base_url = f"https://{domain}"

    # Browser-like headers to reduce 403 blocks
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
    }

    endpoints = ["", "/contact", "/about", "/team", "/leadership"]
    found_emails = set()
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    # Step 1: Scrape direct web pages
    for ep in endpoints:
        target_url = urljoin(base_url, ep)
        try:
            res = requests.get(target_url, headers=headers, timeout=4)
            if res.status_code == 200:
                matches = re.findall(email_regex, res.text)
                for email in matches:
                    e = email.lower()
                    if (
                        domain in e
                        and not e.endswith(
                            (".png", ".jpg", ".jpeg", ".svg", ".js", ".css")
                        )
                    ):
                        found_emails.add(e)
        except Exception:
            continue

    results = []

    # Step 2: Convert scraped emails
    for email in found_emails:
        prefix = email.split("@")[0]
        parts = prefix.split(".")
        first_name = parts[0].capitalize() if len(parts) > 0 else "Unknown"
        last_name = parts[1].capitalize() if len(parts) > 1 else ""

        results.append(
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "position": "Discovered Contact",
                "source": "Web Crawler",
            }
        )

    # Step 3: Fallback Pattern Generator if scraping yielded 0
    if not results:
        company_name = domain.split(".")[0].capitalize()

        # Generates standard operational role patterns for the target domain
        patterns = [
            ("Quality Assurance", "Manager", f"qa@{domain}"),
            ("Food Safety", "Director", f"foodsafety@{domain}"),
            ("Data", "Analyst", f"data@{domain}"),
            ("Compliance", "Officer", f"compliance@{domain}"),
        ]

        for first, last, email in patterns:
            results.append(
                {
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "position": f"{first} {last}",
                    "source": "Pattern Generator",
                }
            )

    return {"target": req.target, "results": results}
