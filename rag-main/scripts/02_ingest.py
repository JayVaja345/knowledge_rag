"""
Step 2 — ingest a Cloudinary PDF into the company graph.
Usage:
  python -m scripts.02_ingest --url <cloudinary_url> --company <company_id>
  python -m scripts.02_ingest --url <url> --company <company_id> --title "Q3 Report"
"""
import asyncio
import argparse
import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph_client import build_graphiti
from src.ingest.loaders import load_cloudinary_file
from src.ingest.ingest import ingest_docs


async def main(url: str, company_id: str, title: str | None, min_conf: float):
    doc = load_cloudinary_file(url, company_id=company_id, title=title)
    if doc is None:
        print("Failed to load or parse doc. Aborting.")
        return

    print(f"Loaded: {doc.title} ({len(doc.text)} chars)")

    g = build_graphiti()
    try:
        stats = await ingest_docs(
            graphiti=g,
            docs=[doc],
            company_id=company_id,
            min_conf=min_conf,
        )
        print(f"\nDone. {stats['episodes']} episodes ingested, {stats['rejected']} rejected.")
    finally:
        await g.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     required=True,  help="Cloudinary PDF URL")
    parser.add_argument("--company", required=True,  help="Company ID")
    parser.add_argument("--title",   default=None,   help="Optional document title")
    parser.add_argument("--min-conf", type=float, default=0.0, help="Min classification confidence")
    args = parser.parse_args()
   
    asyncio.run(main(args.url, args.company, args.title, args.min_conf))  