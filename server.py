import os
import re
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

GOOGLE_API_KEY = "AIzaSyD02UwigOMvHpaUSIL5rqhUQ8SrSIh0bGc"
GOOGLE_CX = "523cc902190574994"


class TargetRequest(BaseModel):
    target: str


def resolve_domain(company_name: str) -> str:
    cleaned = re.sub(r"\(.*?\)", "", company_name).strip()
    if "." in cleaned and " " not in cleaned:
        return cleaned.lower()

    try:
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={requests.utils.quote(cleaned)}"
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200 and resp.json():
            return resp.json()[0]["domain"].lower()
    except Exception:
        pass

    slug = re.sub(r"[^\w]", "", cleaned.lower())
    return f"{slug}.com"


@app.post("/scrape")
def scrape_employee_leads(req: TargetRequest):
    domain = resolve_domain(req.target)
    company_name = domain.split(".")[0]
    roles = ["Quality", "Operations", "Safety"]

    discovered_leads = []
    seen_emails = set()

    for role in roles:
        query = f'site:linkedin.com/in/ "{company_name}" "{role}"'
        url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={requests.utils.quote(query)}"

        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                items = res.json().get("items", [])
                for item in items:
                    snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
                    names = re.findall(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", snippet)

                    for full_name in names:
                        first, last = full_name.split(" ")[0], full_name.split(" ")[1]
                        email_candidate = f"{first.lower()}.{last.lower()}@{domain}"

                        if email_candidate not in seen_emails:
                            seen_emails.add(email_candidate)
                            discovered_leads.append(
                                {
                                    "email": email_candidate,
                                    "first_name": first,
                                    "last_name": last,
                                    "position": f"{role} Specialist",
                                    "source": "Google Official API",
                                }
                            )
        except Exception as e:
            print(f"API Error: {e}")

    # Fallback pattern if API yields no names
    if not discovered_leads:
        discovered_leads.append(
            {
                "email": f"quality@{domain}",
                "first_name": "Quality Assurance",
                "last_name": "Department",
                "position": "QA Inbox",
                "source": "Domain Pattern Generator",
            }
        )

    return {"target": req.target, "results": discovered_leads}
