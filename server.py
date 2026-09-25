import re
from urllib.parse import urljoin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

app = FastAPI()

# Allow frontend HTML UI to make requests to local python worker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TargetRequest(BaseModel):
    target: str


def format_domain(target: str) -> str:
    target = target.strip().lower()
    if not target.startswith("http://") and not target.startswith("https://"):
        if "." not in target:
            target = f"{target}.com"
        return f"https://{target}"
    return target


@app.post("/scrape")
def scrape_emails(req: TargetRequest):
    domain_url = format_domain(req.target)
    base_domain = domain_url.replace("https://", "").replace("http://", "")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
    }

    endpoints = ["", "/contact", "/about", "/team", "/our-team"]
    found_emails = set()
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    for ep in endpoints:
        target_url = urljoin(domain_url, ep)
        try:
            res = requests.get(target_url, headers=headers, timeout=4)
            if res.status_code == 200:
                matches = re.findall(email_regex, res.text)
                for email in matches:
                    e = email.lower()
                    if not e.endswith(
                        (
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".webp",
                            ".js",
                            ".css",
                        )
                    ):
                        found_emails.add(e)
        except Exception:
            continue

    # Convert extracted emails into structured UI objects
    results = []
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

    return {"target": req.target, "results": results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
