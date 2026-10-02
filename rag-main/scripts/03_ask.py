"""
Step 3 — ask questions against the company graph.
Usage:
  python -m scripts.03_ask --company <company_id> "What is the recruitment policy?"
  python -m scripts.03_ask --company <company_id>   # interactive loop
"""
import asyncio
import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph_client import build_graphiti
from src.retrieval.retrieve import ask


async def main(company_id: str, question: str | None):
    g = build_graphiti()
    try:
        if question:
            print(await ask(g, question, company_id))
            return

        print(f"Asking company graph for '{company_id}' (Ctrl-C to exit).")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q: 
                print(await ask(g, q, company_id))
    finally:
        await g.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True, help="Company ID")
    parser.add_argument("question",  nargs="?",     help="Question (omit for interactive mode)")
    args = parser.parse_args()

    asyncio.run(main(args.company, args.question))