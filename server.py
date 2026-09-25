import concurrent.futures
import re
from urllib.parse import urlparse
from duckduckgo_search import DDGS
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


def resolve_company_to_domain(company_name: str) -> str:
    """Uses Clearbit's free autocomplete API to turn company names into exact domains."""
    raw_input = company_name.strip()

    # If already a domain format, return directly
    if "." in raw_input and " " not in raw_input and "(" not in raw_input:
        return raw_input.lower()

    # Clean parentheses and legal suffixes
    cleaned_name = re.sub(r"\(.*?\)", "", raw_input).strip()

    # Query Clearbit's public company name suggestion API
    try:
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={requests.utils.quote(cleaned_name)}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                domain = data[0].get("domain")
                if domain:
                    return domain.lower()
    except Exception as e:
        print(f"Clearbit Lookup Error: {e}")

    # Fallback slug generator if API fails
    slug = re.sub(r"[^\w]", "", cleaned_name.lower())
    suffixes = [
        "inc",
        "llc",
        "corp",
        "corporation",
        "company",
        "group",
        "ltd",
        "usa",
    ]
    for s in suffixes:
        if slug.endswith(s) and len(slug) > len(s):
            slug = slug[: -len(s)]

    return f"{slug}.com"


def fetch_ddg_results(query: str):
    try:
        with DDGS(timeout=3) as ddgs:
            return list(ddgs.text(query, max_results=3))
    except Exception as e:
        print(f"DDG Search Error: {e}")
        return []


@app.post("/scrape")
def scrape_employee_leads(req: TargetRequest):
    domain = resolve_company_to_domain(req.target)
    company_name = domain.split(".")[0]

    target_roles = ["Quality", "Operations", "Safety"]
    discovered_leads = []
    seen_emails = set()

    # Words to ignore when parsing names from search snippets
    ignore_words = {
        "LinkedIn",
        "Profile",
        "United",
        "States",
        "Greater",
        "Area",
        "Manager",
        "Director",
        "Quality",
        "Safety",
        "Company",
        "Inc",
        "LLC",
        "Wikipedia",
        "Resort",
        "Airlines",
        "Founded",
        "Department",
        "Lead",
        "Operations",
        "Foods",
        "Bakery",
        "Products",
        "See",
        "View",
        "About",
        "Contact",
        "Japan",
        "Spent",
        "Retirement",
        "Planning",
        "Spanish",
        "Translation",
        "West",
        "Haven",
    }

    for role in target_roles:
        query = f'site:linkedin.com/in/ "{company_name}" "{role}"'

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_ddg_results, query)
                results = future.result(timeout=3.5)

                for res in results:
                    link = res.get("href", "")

                    # Verify result is an actual LinkedIn profile link
                    if "linkedin.com/in/" not in link:
                        continue

                    title_text = res.get("title", "")
                    snippet_text = res.get("body", "")
                    combined = f"{title_text} {snippet_text}"

                    names = re.findall(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", combined)

                    for full_name in names:
                        parts = full_name.split(" ")
                        first, last = parts[0], parts[1]

                        if (
                            first in ignore_words
                            or last in ignore_words
                            or first.lower() == company_name.lower()
                            or last.lower() == company_name.lower()
                        ):
                            continue

                        email_candidate = (
                            f"{first.lower()}.{last.lower()}@{domain}"
                        )

                        if email_candidate not in seen_emails:
                            seen_emails.add(email_candidate)
                            discovered_leads.append(
                                {
                                    "email": email_candidate,
                                    "first_name": first,
                                    "last_name": last,
                                    "position": f"{role} Specialist",
                                    "source": "Search Engine Scraper",
                                }
                            )
        except Exception as e:
            print(f"Search Execution Error: {e}")

    # Fallback to clean, domain-matched department emails
    if not discovered_leads:
        fallback_depts = [
            ("quality", "Quality Assurance", "QA Inbox"),
            ("operations", "Operations", "Ops Inbox"),
            ("safety", "Food Safety", "Safety Inbox"),
        ]

        for dept_prefix, dept_name, role_title in fallback_depts:
            discovered_leads.append(
                {
                    "email": f"{dept_prefix}@{domain}",
                    "first_name": dept_name,
                    "last_name": "Department",
                    "position": role_title,
                    "source": "Domain Pattern Generator",
                }
            )

    return {"target": req.target, "results": discovered_leads}
