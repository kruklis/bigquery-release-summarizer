#!/usr/bin/env python3
"""
BigQuery Release Notes Fetcher & Summarizer CLI & Entrypoint
"""

import sys
import os
import argparse
from datetime import datetime

from fetcher import ReleaseNotesFetcher
from summarizer import ReleaseNotesSummarizer
from server import run_server


def print_banner():
    print("""
┌─────────────────────────────────────────────────────────────┐
│       BigQuery Release Notes Fetcher & AI Summarizer        │
│          Google Cloud Solutions Architecture Tool           │
└─────────────────────────────────────────────────────────────┘
""")


def cmd_fetch(args):
    fetcher = ReleaseNotesFetcher()
    items = fetcher.get_flat_items(
        force_refresh=args.refresh,
        days=args.days,
        category=args.category,
        stage=args.stage,
        search=args.search
    )

    print(f"\n📦 Retrieved {len(items)} release updates")
    if args.days:
        print(f"⏱ Filter: Last {args.days} days")
    if args.category and args.category.lower() != "all":
        print(f"🏷 Category: {args.category}")
    if args.stage and args.stage.lower() != "all":
        print(f"🚀 Launch Stage: {args.stage}")
    if args.search:
        print(f"🔍 Search: '{args.search}'")
    print("-" * 65)

    for it in items:
        badge_stage = f"[{it['stage']}]" if it['stage'] != "General" else ""
        print(f"• {it['date']} | {it['category']:<12} {badge_stage:<10}")
        print(f"  {it['text'][:120]}..." if len(it['text']) > 120 else f"  {it['text']}")
        if it['entry_url']:
            print(f"  🔗 {it['entry_url']}")
        print()


def cmd_stats(args):
    fetcher = ReleaseNotesFetcher()
    stats = fetcher.get_stats()
    print("\n📊 BigQuery Release Notes Summary Statistics")
    print("=" * 45)
    print(f"Total Individual Updates: {stats['total_items']}")
    print(f"Total Release Date Drops: {stats['total_entries']}")
    print("\nCategories:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
        print(f"  • {cat:<15}: {count}")
    print("\nLaunch Stages:")
    for stg, count in sorted(stats['stages'].items(), key=lambda x: x[1], reverse=True):
        print(f"  • {stg:<15}: {count}")
    print()


def cmd_summarize(args):
    fetcher = ReleaseNotesFetcher()
    summarizer = ReleaseNotesSummarizer()

    print(f"\n🧠 Analyzing BigQuery release updates (Last {args.days or 'all'} days)...")
    items = fetcher.get_flat_items(
        force_refresh=args.refresh,
        days=args.days,
        category=args.category,
        stage=args.stage,
        search=args.search
    )

    if not items:
        print("❌ No release updates found matching your criteria.")
        return

    timeframe_desc = f"Last {args.days} days" if args.days else "All available release notes"
    result = summarizer.summarize(
        items=items,
        mode=args.mode,
        custom_question=args.query,
        force_offline=args.offline,
        timeframe_desc=timeframe_desc
    )

    print(f"⚡ Synthesized using engine: [{result['engine']}] (mode: {result['mode']})\n")
    print("=" * 65)
    print(result["summary"])
    print("=" * 65)

    if args.export:
        export_path = os.path.abspath(args.export)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(result["summary"])
        print(f"\n💾 Summary successfully exported to: {export_path}")


def cmd_serve(args):
    run_server(port=args.port, host=args.host)


def main():
    parser = argparse.ArgumentParser(
        description="BigQuery Release Notes Ingestion, Summarization & Web Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 main.py --fetch --days 14
  python3 main.py --summarize --days 30 --mode executive
  python3 main.py --summarize --query "What changed with JDBC and drivers?"
  python3 main.py --summarize --days 30 --export bigquery_monthly_brief.md
  python3 main.py --serve --port 8080
"""
    )

    parser.add_argument("--fetch", action="store_true", help="Fetch and print release items to console")
    parser.add_argument("--summarize", action="store_true", help="Generate executive, technical, or custom AI summary")
    parser.add_argument("--stats", action="store_true", help="Display breakdown statistics")
    parser.add_argument("--serve", action="store_true", help="Start the interactive Web UI dashboard server")
    
    # Options
    parser.add_argument("--days", type=int, default=None, help="Filter updates to the last N days (e.g. 7, 14, 30, 90)")
    parser.add_argument("--category", type=str, default="all", help="Filter by category (Feature, Change, Fixed, Announcement, Deprecated)")
    parser.add_argument("--stage", type=str, default="all", help="Filter by launch stage (GA, Preview)")
    parser.add_argument("--search", type=str, default=None, help="Filter by keyword search")
    parser.add_argument("--mode", type=str, default="executive", choices=["executive", "architect", "digest"], help="Summary style")
    parser.add_argument("--query", type=str, default=None, help="Custom prompt or question to ask about the release notes")
    parser.add_argument("--offline", action="store_true", help="Force fast rule-based analytical summary without calling LLM")
    parser.add_argument("--refresh", action="store_true", help="Force fresh download from Google Cloud XML feed")
    parser.add_argument("--export", type=str, default=None, help="File path to save the generated Markdown summary")
    parser.add_argument("--port", type=int, default=8080, help="Port for the web server (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address for the web server (default: 0.0.0.0)")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        print_banner()
        parser.print_help()
        sys.exit(0)

    if args.serve:
        cmd_serve(args)
    elif args.summarize:
        cmd_summarize(args)
    elif args.fetch:
        cmd_fetch(args)
    elif args.stats:
        cmd_stats(args)
    elif args.refresh:
        fetcher = ReleaseNotesFetcher()
        entries = fetcher.fetch_live()
        print(f"✅ Successfully refreshed feed. Total entries: {len(entries)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
