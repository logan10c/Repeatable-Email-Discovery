import concurrent.futures
import re
from urllib.parse import quote, urlparse
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
    """Uses Clearbit Autocomplete API to accurately convert raw company names to domains."""
    raw_input = company_name.strip()

    # Return immediately if the user provided a direct domain
    if "." in raw_input and " " not in raw_input and "(" not in raw_input:
        return raw_input.lower()

    # Clean legal suffixes and parentheticals
    cleaned_name = re.sub(r"\(.*?\)", "", raw_input).strip()

    # 1. Try Clearbit API (Fast & highly accurate)
    try:
        api_url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={quote(cleaned_name)}"
        res = requests.get(api_url, timeout=2)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                domain = data[0].get("domain")
                if domain:
                    return domain.lower()
    except Exception as e:
        print(f"Clearbit API Lookup Error: {e}")

    # 2. Hardcoded fallback rules for common edge cases
    slug = re.sub(r"[^\w]", "", cleaned_name.lower())
    suffixes = [
        "inc",
        "llc",
        "corp",
        "corporation",
        "company",
        "group",
        "ltd",
        "co",
    ]
    for s in suffixes:
        if slug.endswith(s) and len(slug) > len(s):
            slug = slug[: -len(s)]

    return f"{slug}.com"


@app.post("/scrape")
def scrape_employee_leads(req: TargetRequest):
    domain = resolve_company_to_domain(req.target)

    # Standard departmental target patterns
    fallback_depts = [
        ("quality", "Quality Assurance", "QA Inbox"),
        ("operations", "Operations", "Ops Inbox"),
        ("safety", "Food Safety", "Safety Inbox"),
    ]

    discovered_leads = []

    for dept_prefix, dept_name, role_title in fallback_depts:
        discovered_leads.append(
            {
                "email": f"{dept_prefix}@{domain}",
                "first_name": dept_name,
                "last_name": "Department",
                "position": role_title,
                "source": "Clearbit Domain Resolver",
            }
        )

    return {"target": req.target, "results": discovered_leads}
