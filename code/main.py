from __future__ import annotations
import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

ESCALATION_KEYWORDS = {
    "fraud", "stolen", "unauthorized", "chargeback", "charge", "lawsuit", "legal", "security", "breach", "violation", "harass", "threat", "urgent", "immediately", "locked out", "can\'t login", "cannot login", "hacked", "scam", "phishing", "lost card", "lost access", "suspicious"
}

PRODUCT_HINTS = {
    "billing": ["bill", "invoice", "payment", "charge", "refund", "subscription"],
    "login_account": ["login", "password", "account", "sign in", "sso", "scim"],
    "integrations": ["slack", "zoom", "webex", "github", "connector", "integration"],
    "interviews_assessments": ["interview", "assessment", "test", "candidate", "proctor"],
    "travel_cards": ["visa", "travel", "exchange", "card", "merchant", "consumer"],
}

@dataclass
class Doc:
    path: str
    text: str


# normalize text
def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()

# tokenize text by extracting important keywords
def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", normalize(text))


# load reference documents
def load_docs(data_root: Path) -> List[Doc]:
    docs: List[Doc] = []
    for p in data_root.rglob("*.md"):
        try:
            docs.append(Doc(path=str(p), text=p.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            continue
    return docs


# find the best matching document for an issue
def best_doc(issue: str, docs: List[Doc], company: str) -> Doc | None:
    q = tokenize(issue)
    if not q:
        return None
    qset = set(q)
    scoped = docs
    company_l = normalize(company)
    if "hackerrank" in company_l:
        scoped = [d for d in docs if "/hackerrank/" in d.path]
    elif "claude" in company_l:
        scoped = [d for d in docs if "/claude/" in d.path]
    elif "visa" in company_l:
        scoped = [d for d in docs if "/visa/" in d.path]
    if not scoped:
        scoped = docs
    best, best_score = None, -1
    for d in scoped:
        tokens = set(tokenize(d.text[:6000] + " " + d.path))
        score = len(qset & tokens)
        if score > best_score:
            best, best_score = d, score
    return best


# classify the request type as feature_request, bug, product_issue, or invalid
def classify_request(issue: str) -> str:
    text = normalize(issue)
    if any(w in text for w in ["feature", "add", "would like", "can you support", "request"]):
        return "feature_request"
    if any(w in text for w in ["bug", "error", "not working", "fails", "crash"]):
        return "bug"
    if len(text) < 8:
        return "invalid"
    return "product_issue"


# classify product area
def classify_product_area(issue: str, company: str) -> str:
    txt = normalize(issue)
    for area, kws in PRODUCT_HINTS.items():
        if any(k in txt for k in kws):
            return f"{company or 'general'}:{area}"
    return f"{company or 'general'}:general_support"


# escalation logic: escalate if any tokens exist in ESCALATION_KEYWORDS, or if the best document has very less mentions about the issue
def should_escalate(issue: str, best: Doc | None) -> bool:
    txt = normalize(issue)
    if any(k in txt for k in ESCALATION_KEYWORDS):
        return True
    if best is None:
        return True
    overlap = len(set(tokenize(issue)) & set(tokenize(best.text[:5000])))
    return overlap < 2


# generate response for an issue
def generate_response(issue: str, company: str, status: str, best: Doc | None) -> str:
    if status == "escalated":
        return (
            "Thanks for reporting this issue. It will be escalated to a human support specialist for further asistance since it appears to be sensitive or needs account-level review."
        )
    source = Path(best.path).name if best else "support docs"
    return (
        f"Thanks for reaching out about {company or 'your request'}. Please follow the product's documentation ({source}) for further assistance."
    )


# function to run the business logic
def run(input_csv: Path, output_csv: Path, data_root: Path) -> None:
    docs = load_docs(data_root)  # load reference documents
    with input_csv.open("r", encoding="utf-8", newline="") as f:  # read input CSV
        rows = list(csv.DictReader(f))

    fieldnames = ["status", "product_area", "response", "justification", "request_type"]
    with output_csv.open("w", encoding="utf-8", newline="") as f:  # write output CSV
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            lowered = {str(k).strip().lower(): v for k, v in row.items()}
            issue = lowered.get("issue", "")
            company = lowered.get("company", "None")
            best = best_doc(issue, docs, company)  # find best matching document
            req_type = classify_request(issue)  # classify request type
            status = "escalated" if should_escalate(issue, best) else "replied"  # determine escalation
            p_area = classify_product_area(issue, company)  # classify product area
            response = generate_response(issue, company, status, best)  # generate response
            justification = (
                f"request_type={req_type}; status={status}; "
                f"matched_doc={(Path(best.path).name if best else 'none')}"
            )  # create justification
            writer.writerow(
                {
                    "status": status,
                    "product_area": p_area,
                    "response": response,
                    "justification": justification,
                    "request_type": req_type,
                }
            )


# resolve relative or absolute paths based on repo root
def resolve_path(raw: str, repo_root: Path) -> Path:
    normalized = raw.replace("\\", "/")
    p = Path(normalized)
    if p.is_absolute():
        return p
    return repo_root / p


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal support triage agent")
    parser.add_argument("--input", default="support_tickets/support_tickets.csv", help="Path to input CSV file")
    parser.add_argument("--output", default="support_tickets/output.csv", help="Path to output CSV file")
    parser.add_argument("--data", default="data", help="Path to data directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    input_csv = resolve_path(args.input, repo_root)
    output_csv = resolve_path(args.output, repo_root)
    data_root = resolve_path(args.data, repo_root)

    run(input_csv, output_csv, data_root)
    print(f"Wrote predictions to {output_csv}")


if __name__ == "__main__":
    main()