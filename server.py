import concurrent.futures
import os
import re
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


def fetch_ddg_results(query: str):
    """Executes DDG search with a hard internal limit."""
    try:
        with DDGS(timeout=3) as ddgs:
            return list(ddgs.text(query, max_results=3))
    except Exception as e:
        print(f"DDG Search Error: {e}")
        return []


@app.post("/scrape")
def scrape_employee_leads(req: TargetRequest):
    domain = clean_domain(req.target)
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
    }

    # Attempt search engine scraping with a strict 3-second timeout
    for role in target_roles:
        query = f'site:linkedin.com/in/ "{company_name}" "{role}"'

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_ddg_results, query)
                results = future.result(
                    timeout=3.5
                )  # Hard break after 3.5 seconds

                for res in results:
                    title_text = res.get("title", "")
                    snippet_text = res.get("body", "")
                    combined = f"{title_text} {snippet_text}"

                    # Regex for First Last names
                    names = re.findall(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", combined)

                    for full_name in names:
                        parts = full_name.split(" ")
                        first, last = parts[0], parts[1]

                        if first in ignore_words or last in ignore_words:
                            continue

                        email_candidate = f"{first.lower()}.{last.lower()}@{domain}"

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
        except concurrent.futures.TimeoutError:
            print(f"DDG Search timed out for query: {query}")
        except Exception as e:
            print(f"Search Execution Error: {e}")

    # Fallback pattern generator if search scraping is blocked or times out
    if not discovered_leads:
        roles_data = [
            ("Quality Assurance", "QA Director"),
            ("Operations Lead", "Ops Manager"),
            ("Supply Chain", "Logistics Coordinator"),
        ]

        for dept, role in roles_data:
            dept_key = dept.lower().replace(" ", "")
            discovered_leads.append(
                {
                    "email": f"{dept_key}@{domain}",
                    "first_name": dept,
                    "last_name": "Department",
                    "position": role,
                    "source": "Domain Pattern Generator",
                }
            )

    return {"target": req.target, "results": discovered_leads}
