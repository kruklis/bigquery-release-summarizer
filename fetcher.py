#!/usr/bin/env python3
"""
BigQuery Release Notes Ingestion & Parsing Engine
Fetches from official Atom XML feed with local caching and item enrichment.
"""

import os
import re
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

FEED_URL = "https://cloud.google.com/feeds/bigquery-release-notes.xml"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "release_notes.json")
CACHE_TTL_SECONDS = 3600  # 1 hour


def clean_html_to_text(html_str: str) -> str:
    """Converts HTML markup to clean readable plain text."""
    if not html_str:
        return ""
    # Replace link tags with text
    text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', html_str, flags=re.IGNORECASE)
    # Remove all other tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Unescape common entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    # Collapse multiple whitespaces
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def extract_links(html_str: str) -> List[Dict[str, str]]:
    """Extracts all hyperlinks from an HTML fragment."""
    links = []
    if not html_str:
        return links
    pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html_str):
        url = match.group(1).strip()
        anchor = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if url and anchor:
            links.append({"text": anchor, "url": url})
    return links


def detect_stage(text: str, html: str) -> str:
    """Identifies the launch stage (GA, Preview, or General)."""
    combined = f"{text} {html}".lower()
    if re.search(r'\b(generally available|\(ga\)|general availability)\b', combined):
        return "GA"
    elif re.search(r'\b(in preview|preview)\b', combined):
        return "Preview"
    return "General"


def parse_atom_feed(xml_content: str) -> List[Dict[str, Any]]:
    """
    Parses Atom feed XML into structured release notes entries and granular items.
    """
    root = ET.fromstring(xml_content)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries_data = []

    for entry in root.findall('atom:entry', ns):
        entry_id = entry.findtext('atom:id', default='', namespaces=ns)
        date_title = entry.findtext('atom:title', default='', namespaces=ns).strip()
        updated = entry.findtext('atom:updated', default='', namespaces=ns).strip()
        
        link_elem = entry.find('atom:link', ns)
        link_href = link_elem.attrib.get('href', '') if link_elem is not None else ''

        content_elem = entry.find('atom:content', ns)
        content_html = content_elem.text if content_elem is not None and content_elem.text else ''

        # Parse granular items inside content HTML
        items = []
        if '<h3>' in content_html:
            parts = re.split(r'<h3>(.*?)</h3>', content_html, flags=re.IGNORECASE)
            for i in range(1, len(parts), 2):
                cat = parts[i].strip()
                item_html = parts[i + 1].strip() if i + 1 < len(parts) else ''
                clean_text = clean_html_to_text(item_html)
                stage = detect_stage(clean_text, item_html)
                links = extract_links(item_html)

                items.append({
                    "id": f"{entry_id}#item-{len(items)+1}",
                    "category": cat or "General",
                    "stage": stage,
                    "text": clean_text,
                    "html": item_html,
                    "links": links
                })
        else:
            clean_text = clean_html_to_text(content_html)
            stage = detect_stage(clean_text, content_html)
            items.append({
                "id": f"{entry_id}#item-1",
                "category": "General",
                "stage": stage,
                "text": clean_text,
                "html": content_html,
                "links": extract_links(content_html)
            })

        entries_data.append({
            "id": entry_id,
            "title": date_title,
            "updated": updated,
            "url": link_href,
            "item_count": len(items),
            "items": items
        })

    return entries_data


class ReleaseNotesFetcher:
    """Manages fetching, caching, and querying BigQuery release notes."""

    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

    def fetch_live(self) -> List[Dict[str, Any]]:
        """Downloads the Atom feed directly from Google Cloud."""
        req = urllib.request.Request(
            FEED_URL,
            headers={
                "User-Agent": "BigQueryReleaseSummarizer/1.0 (Google Cloud Engineer Assistant; Python)"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode('utf-8', errors='replace')
        entries = parse_atom_feed(xml_data)
        
        # Save to cache
        cache_payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "feed_url": FEED_URL,
            "total_entries": len(entries),
            "entries": entries
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, indent=2, ensure_ascii=False)

        return entries

    def get_notes(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves release notes from cache if fresh, otherwise fetches live.
        """
        if not force_refresh and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fetched_at_str = data.get("fetched_at")
                if fetched_at_str:
                    fetched_at = datetime.fromisoformat(fetched_at_str)
                    age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
                    if age_seconds < CACHE_TTL_SECONDS:
                        return data.get("entries", [])
            except Exception as e:
                print(f"[Warning] Cache read failed: {e}. Refetching live...")

        return self.fetch_live()

    def get_flat_items(self, force_refresh: bool = False, days: Optional[int] = None,
                       category: Optional[str] = None, stage: Optional[str] = None,
                       search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns a flat list of individual release items with entry metadata attached,
        filtered by parameters.
        """
        entries = self.get_notes(force_refresh=force_refresh)
        flat_items = []

        cutoff_date = None
        if days is not None and days > 0:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        for entry in entries:
            entry_updated = entry.get("updated")
            entry_dt = None
            if entry_updated:
                try:
                    entry_dt = datetime.fromisoformat(entry_updated)
                except Exception:
                    pass

            if cutoff_date and entry_dt and entry_dt < cutoff_date:
                continue

            for item in entry.get("items", []):
                # Category filter
                if category and category.lower() != "all" and item.get("category", "").lower() != category.lower():
                    continue

                # Stage filter
                if stage and stage.lower() != "all" and item.get("stage", "").lower() != stage.lower():
                    continue

                # Search query filter
                if search:
                    q = search.lower()
                    haystack = f"{item.get('text', '')} {item.get('category', '')} {entry.get('title', '')}".lower()
                    if q not in haystack:
                        continue

                flat_items.append({
                    "id": item["id"],
                    "date": entry["title"],
                    "updated": entry["updated"],
                    "entry_url": entry["url"],
                    "category": item["category"],
                    "stage": item["stage"],
                    "text": item["text"],
                    "html": item["html"],
                    "links": item["links"]
                })

        return flat_items

    def get_stats(self) -> Dict[str, Any]:
        """Calculates breakdown metrics for the dashboard."""
        items = self.get_flat_items()
        categories: Dict[str, int] = {}
        stages: Dict[str, int] = {}

        for item in items:
            cat = item.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            stg = item.get("stage", "General")
            stages[stg] = stages.get(stg, 0) + 1

        return {
            "total_items": len(items),
            "total_entries": len(self.get_notes()),
            "categories": categories,
            "stages": stages
        }


if __name__ == "__main__":
    fetcher = ReleaseNotesFetcher()
    print("Testing BigQuery Release Notes Fetcher...")
    notes = fetcher.get_notes(force_refresh=True)
    print(f"Successfully fetched {len(notes)} entries.")
    items = fetcher.get_flat_items(days=30)
    print(f"Total items in last 30 days: {len(items)}")
    stats = fetcher.get_stats()
    print("Stats breakdown:", json.dumps(stats, indent=2))
