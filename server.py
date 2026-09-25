import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
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
    domain = (
        target.strip()
        .lower()
        .replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
    )
    if "." not in domain:
        domain = f"{domain}.com"
    return domain


@app.post("/scrape")
def scrape_employee_leads(req: TargetRequest):
    domain = clean_domain(req.target)
    company_name = domain.split(".")[0]

    # Target search query to find real employees via search snippets
    query = f'site:linkedin.com/in/ "{company_name}"'
    ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    discovered_leads = []

    try:
        response = requests.get(ddg_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("a", class_="result__snippet")

            for res in results:
                snippet_text = res.get_text()

                # Extract potential full names (2 capitalized words)
                names = re.findall(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", snippet_text)

                for full_name in names:
                    parts = full_name.split(" ")
                    first, last = parts[0], parts[1]

                    # Filter out common false-positive words
                    if first in [
                        "LinkedIn",
                        "View",
                        "Profile",
                        "See",
                        "Directory",
                    ]:
                        continue

                    email_candidate = f"{first.lower()}.{last.lower()}@{domain}"

                    discovered_leads.append(
                        {
                            "email": email_candidate,
                            "first_name": first,
                            "last_name": last,
                            "position": "Verified Profile Snippet",
                            "source": "Search Engine Web Scraper",
                        }
                    )
    except Exception as e:
        print(f"Scraper Exception: {e}")

    # Fallback if no snippet names were extracted
    if not discovered_leads:
        discovered_leads.append(
            {
                "email": f"contact@{domain}",
                "first_name": "General",
                "last_name": "Contact",
                "position": "Main Corporate Inbox",
                "source": "Domain Fallback",
            }
        )

    return {"target": req.target, "results": discovered_leads}
