import concurrent.futures
import re
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    """Converts inputs like 'Taylor Farms' or 'Brill (Formerly CSM...)' to 'taylorfarms.com'."""
    raw_input = company_name.strip()

    # If user already typed a clean domain (e.g. "taylorfarms.com"), return it directly
    if "." in raw_input and " " not in raw_input and "(" not in raw_input:
        return raw_input.lower()

    # Clean raw company text
    cleaned_name = re.sub(r"\(.*?\)", "", raw_input).strip()

    try:
        # Search DuckDuckGo for official website link
        with DDGS(timeout=3) as ddgs:
            results = list(
                ddgs.text(f'"{cleaned_name}" official website', max_results=2)
            )
            for res in results:
                link = res.get("href", "")
                parsed = urlparse(link)
                domain = parsed.netloc.lower().replace("www.", "")

                # Filter out search engines, social media, and directory sites
                if domain and not any(
                    x in domain
                    for x in [
                        "linkedin",
                        "facebook",
                        "wikipedia",
                        "duckduckgo",
                        "bloomberg",
                        "dnb.com",
                        "zoominfo",
                    ]
                ):
                    return domain
    except Exception as e:
        print(f"Domain Resolution Error: {e}")

    # Fallback slug generator if DDG resolution times out
    slug = re.sub(r"[^\w]", "", cleaned_name.lower())
    suffixes = ["inc", "llc", "corp", "corporation", "company", "group", "ltd"]
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
    # SECTION 2 INTEGRATION: Resolve company name input to an official clean domain
    domain = resolve_company_to_domain(req.target)
    company_name = domain.split(".")[0]

    target_roles = ["Quality", "Operations", "Safety"]
    discovered_leads = []
    seen_emails = set()

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
    }

    for role in target_roles:
        query = f'site:linkedin.com/in/ "{company_name}" "{role}"'

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_ddg_results, query)
                results = future.result(timeout=3.5)

                for res in results:
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

    # Fallback to clean, valid department emails if no individual names pass filters
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
