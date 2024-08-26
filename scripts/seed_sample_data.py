"""
Seed the demo collection with the sample documents in data/samples/.
Requires the API to be running at APP_URL (default: http://localhost:8000).
"""
import os
import sys
import time
from pathlib import Path

import httpx

APP_URL = os.getenv("APP_URL", "http://localhost:8000")
COLLECTION = "demo"
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"

DOCUMENTS = [
    {
        "path": SAMPLES_DIR / "incident_response_runbook.txt",
        "title": "Incident Response Runbook v3.2",
    },
    {
        "path": SAMPLES_DIR / "api_security_policy.txt",
        "title": "API Security Policy v2.1",
    },
    {
        "path": SAMPLES_DIR / "deployment_checklist.txt",
        "title": "Deployment Checklist v1.8",
    },
]


def wait_for_api(timeout: int = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{APP_URL}/api/v1/health/live", timeout=3)
            if resp.status_code == 200:
                print(f"API is ready at {APP_URL}")
                return
        except httpx.ConnectError:
            pass
        time.sleep(2)
    print("API did not become ready in time", file=sys.stderr)
    sys.exit(1)


def upload_document(client: httpx.Client, doc: dict) -> str:
    path: Path = doc["path"]
    with path.open("rb") as fh:
        resp = client.post(
            f"{APP_URL}/api/v1/documents/upload",
            files={"file": (path.name, fh, "text/plain")},
            data={"title": doc["title"], "collection": COLLECTION},
            timeout=30,
        )
    resp.raise_for_status()
    document_id = resp.json()["id"]
    print(f"  uploaded: {doc['title']} ({document_id})")
    return document_id


def wait_for_ingestion(client: httpx.Client, document_id: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"{APP_URL}/api/v1/documents/{document_id}", timeout=10)
        resp.raise_for_status()
        status = resp.json()["status"]
        if status == "completed":
            chunks = resp.json()["chunk_count"]
            print(f"    ingested: {document_id} ({chunks} chunks)")
            return
        if status == "failed":
            print(f"    failed: {document_id} — {resp.json().get('error_message')}", file=sys.stderr)
            return
        time.sleep(3)
    print(f"    timeout waiting for {document_id}", file=sys.stderr)


def run_demo_query(client: httpx.Client) -> None:
    print("\nRunning demo query...")
    resp = client.post(
        f"{APP_URL}/api/v1/query",
        json={
            "question": "What is the escalation path for a P1 database outage?",
            "collection": COLLECTION,
            "top_k": 3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"Answer: {data['answer'][:300]}...")
    print(f"Sources: {len(data['sources'])} chunks, latency: {data['latency_ms']}ms")


def main() -> None:
    wait_for_api()
    with httpx.Client() as client:
        print(f"\nSeeding collection '{COLLECTION}'...")
        ids = [upload_document(client, doc) for doc in DOCUMENTS]
        print("\nWaiting for ingestion workers...")
        for doc_id in ids:
            wait_for_ingestion(client, doc_id)
        run_demo_query(client)
    print("\nSeed complete.")


if __name__ == "__main__":
    main()
