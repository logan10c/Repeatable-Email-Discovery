import os
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
def find_and_verify_emails(req: TargetRequest):
    domain = clean_domain(req.target)

    # Standard target roles to attempt pattern generation
    target_roles = [
        {"first": "John", "last": "Doe", "pos": "Quality Assurance"},
        {"first": "Jane", "last": "Smith", "pos": "Food Safety Lead"},
        {"first": "Alex", "last": "Johnson", "pos": "Operations Manager"},
    ]

    verified_results = []
    api_key = os.getenv("ANYMAIL_API_KEY", "")

    for person in target_roles:
        first = person["first"]
        last = person["last"]

        # Option A: Check Anymail Finder API if Key is set
        if api_key:
            url = "https://api.anymailfinder.com/v5.0/search/person.json"
            payload = {
                "domain": domain,
                "first_name": first,
                "last_name": last,
            }
            headers = {
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            }

            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=8
                )
                if response.status_code == 200:
                    data = response.json()
                    email = data.get("email")
                    status = data.get("email_class")

                    if email and status == "verified":
                        verified_results.append(
                            {
                                "email": email,
                                "first_name": first,
                                "last_name": last,
                                "position": person["pos"],
                                "source": "API Verified",
                            }
                        )
            except Exception:
                pass

        # Option B: Fallback Local Pattern Permutations
        if not verified_results or not api_key:
            patterns = [
                f"{first.lower()}.{last.lower()}@{domain}",
                f"{first[0].lower()}{last.lower()}@{domain}",
                f"{first.lower()}@{domain}",
            ]

            for email in patterns:
                verified_results.append(
                    {
                        "email": email,
                        "first_name": first,
                        "last_name": last,
                        "position": person["pos"],
                        "source": "Pattern Generator",
                    }
                )

    return {"target": req.target, "results": verified_results}
