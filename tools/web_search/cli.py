"""CLI wrapper — Claude Code agents call this via Bash, humans can too.

  python tools/web_search/cli.py "rust async runtime comparison" 5
"""

import sys
from tool import web_search


def main():
    if len(sys.argv) < 2:
        print('usage: python cli.py "query" [num]', file=sys.stderr)
        sys.exit(1)
    query = sys.argv[1]
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    results = web_search(query, num)
    if not results:
        print("No results.")
        return
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}\n")


if __name__ == "__main__":
    main()
