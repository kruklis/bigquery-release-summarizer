#!/usr/bin/env python3
"""
Summarization Engine for BigQuery Release Notes.
Provides AI synthesis via agy CLI and an analytical rule-based fallback.
"""

import os
import re
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from datetime import datetime

DEFAULT_AGY_PATH = "/usr/local/google/home/kruklis/.local/bin/agy"


def get_agy_path() -> Optional[str]:
    """Finds the agy executable in PATH or default install location."""
    if os.path.exists(DEFAULT_AGY_PATH) and os.access(DEFAULT_AGY_PATH, os.X_OK):
        return DEFAULT_AGY_PATH
    return shutil.which("agy")


def format_items_for_prompt(items: List[Dict[str, Any]], max_items: int = 50) -> str:
    """Formats list of items into structured plain text for the LLM prompt."""
    lines = []
    truncated = items[:max_items]
    for item in truncated:
        date = item.get("date", "Unknown Date")
        cat = item.get("category", "General")
        stage = item.get("stage", "General")
        stage_tag = f"[{stage}] " if stage != "General" else ""
        text = item.get("text", "").strip()
        lines.append(f"- **{date}** | {cat} | {stage_tag}{text}")

    if len(items) > max_items:
        lines.append(f"\n*(Truncated: showing {max_items} out of {len(items)} total items)*")

    return "\n".join(lines)


def build_system_prompt(mode: str, items_text: str, custom_question: Optional[str] = None) -> str:
    """Constructs prompt for agy CLI based on desired mode."""
    if custom_question:
        return f"""You are an expert Google Cloud Data & AI Solutions Architect.
Analyze the following official Google Cloud BigQuery release notes and answer the user's question with precise technical accuracy and actionable insights.

RELEASE NOTES DATA:
{items_text}

USER QUESTION:
{custom_question}

FORMAT:
Provide your response in clean, GitHub-flavored Markdown. Include citations or references to specific launch stages (GA vs Preview) where relevant."""

    if mode == "executive":
        return f"""You are an expert Google Cloud Data & AI Solutions Architect advising enterprise engineering executives and CTOs.
Review the following Google Cloud BigQuery release notes and produce a high-impact Executive Briefing.

RELEASE NOTES DATA:
{items_text}

STRUCTURE YOUR RESPONSE AS FOLLOWS:
# BigQuery Strategic & Executive Briefing

### 1. Executive Summary
Provide a high-impact 2-3 sentence overview synthesizing the overarching direction (e.g. AI convergence, developer ergonomics, governance, cost optimization).

### 2. Key Capabilities & Strategic Themes
Group the most impactful updates under clear themes (e.g., Enterprise GenAI & Analytics, Data Governance & Cost, Developer Productivity & Platform Modernization). Clearly indicate [GA] vs [Preview].

### 3. Business & Operational Impact
Describe how these changes impact time-to-market, cloud spend, and architectural complexity.

### 4. Executive Action Items & Priority Matrix
Provide a clean Markdown table with columns: [Focus Area | Priority (High/Med/Low) | Immediate Recommended Action]."""

    elif mode == "architect":
        return f"""You are a Principal Google Cloud Architect & Lead BigQuery DBA.
Review the following BigQuery release notes and provide a deep Technical Architecture & Migration Guide.

RELEASE NOTES DATA:
{items_text}

STRUCTURE YOUR RESPONSE AS FOLLOWS:
# BigQuery Technical Architecture & Migration Guide

### 1. Breaking Changes, Fixes & Driver Updates
Detail any behavioral changes, updated connectors/drivers (JDBC, ODBC, Python, Rust), and bug fixes. Note any migration actions required.

### 2. SQL Syntax, Modeling & Engine Enhancements
Highlight new SQL functions, table constructs (e.g. identity columns, partitioned tables), and engine improvements. Include syntax/usage notes where applicable.

### 3. AI, BQML & Foundation Models
Analyze updates to BigQuery ML, vector search, foundation models (e.g. TabFM), and GenAI quotas.

### 4. Architectural Recommendations & Best Practices
Provide concrete advice for data engineering teams on adopting GA features immediately vs safely experimenting with Preview features."""

    else:  # 'digest' or default
        return f"""You are an expert Google Cloud Data Engineer.
Review the following BigQuery release notes and produce a concise, well-structured Changelog Digest.

RELEASE NOTES DATA:
{items_text}

STRUCTURE YOUR RESPONSE AS FOLLOWS:
# BigQuery Release Digest

### 🚀 Highlights (Generally Available)
Bullet list of major GA launches with brief technical descriptions.

### 🧪 Preview & Early Access
Bullet list of features entering Preview with key developer use-cases.

### 🔧 Fixes, Changes & Connectors
Bullet list of bug fixes, driver updates, and behavioral modifications.

### 💡 Quick Takeaways for Developers
2-3 actionable bullet points summarizing what developers should start using today."""


class ReleaseNotesSummarizer:
    """Summarizes BigQuery release items using agy CLI or offline heuristic analysis."""

    def __init__(self, agy_path: Optional[str] = None):
        self.agy_path = agy_path or get_agy_path()

    def summarize_with_agy(self, items: List[Dict[str, Any]], mode: str = "executive",
                           custom_question: Optional[str] = None, timeout: int = 120) -> str:
        """Executes agy CLI with the release notes prompt."""
        if not self.agy_path or not os.path.exists(self.agy_path):
            raise RuntimeError(f"Antigravity CLI ('agy') not found at {self.agy_path}. Fall back to analytical mode.")

        items_text = format_items_for_prompt(items)
        prompt = build_system_prompt(mode, items_text, custom_question)

        cmd = [self.agy_path, "-p", prompt]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or f"agy exited with code {result.returncode}"
            raise RuntimeError(f"agy execution failed: {error_msg}")

        return result.stdout.strip()

    def summarize_analytical(self, items: List[Dict[str, Any]], timeframe_desc: str = "Selected Period") -> str:
        """Generates a rule-based analytical summary without requiring LLM calls."""
        if not items:
            return "No release notes found matching the selected criteria."

        ga_items = [it for it in items if it.get("stage") == "GA"]
        preview_items = [it for it in items if it.get("stage") == "Preview"]
        change_items = [it for it in items if it.get("category") in ("Change", "Fixed", "Issue", "Deprecated")]
        feature_items = [it for it in items if it.get("category") == "Feature"]

        # Keyword clustering
        clusters = {
            "AI / ML & Analytics": [],
            "Core SQL & Data Modeling": [],
            "Pipelines, Git & Tools": [],
            "Drivers, SDKs & Connectivity": [],
            "Governance & Quotas": []
        }

        for it in items:
            text_lower = it.get("text", "").lower()
            placed = False
            if any(k in text_lower for k in ["tabfm", "ai.", "conversational", "generative", "model", "predict"]):
                clusters["AI / ML & Analytics"].append(it)
                placed = True
            if any(k in text_lower for k in ["sql", "identity column", "table", "column", "graph"]):
                clusters["Core SQL & Data Modeling"].append(it)
                placed = True
            if any(k in text_lower for k in ["pipeline", "git", "folder", "code asset"]):
                clusters["Pipelines, Git & Tools"].append(it)
                placed = True
            if any(k in text_lower for k in ["driver", "jdbc", "odbc", "sdk", "rust"]):
                clusters["Drivers, SDKs & Connectivity"].append(it)
                placed = True
            if any(k in text_lower for k in ["quota", "cost", "token", "security"]):
                clusters["Governance & Quotas"].append(it)
                placed = True
            if not placed and it.get("category") == "Feature":
                clusters["Core SQL & Data Modeling"].append(it)

        output = [
            f"# BigQuery Release Summary ({timeframe_desc})",
            "",
            f"**Total Updates:** {len(items)} | **GA Launches:** {len(ga_items)} | **Preview Features:** {len(preview_items)} | **Fixes/Changes:** {len(change_items)}",
            "",
            "---",
            "",
            "### 🌟 Generally Available (Production-Ready)",
        ]

        if ga_items:
            for it in ga_items[:8]:
                output.append(f"- **{it.get('date')}** ({it.get('category')}): {it.get('text')}")
        else:
            output.append("- No GA announcements in this selection.")

        output.extend([
            "",
            "### 🧪 In Preview (Early Evaluation)",
        ])

        if preview_items:
            for it in preview_items[:8]:
                output.append(f"- **{it.get('date')}** ({it.get('category')}): {it.get('text')}")
        else:
            output.append("- No Preview announcements in this selection.")

        output.extend([
            "",
            "### 📂 Thematic Grouping",
        ])

        for theme, theme_items in clusters.items():
            if theme_items:
                output.append(f"\n#### {theme} ({len(theme_items)} updates)")
                for it in theme_items[:5]:
                    output.append(f"- [{it.get('stage', 'General')}] **{it.get('date')}**: {it.get('text')}")

        if change_items:
            output.extend([
                "",
                "### ⚠️ Changes, Fixes & Maintenance",
            ])
            for it in change_items:
                output.append(f"- **{it.get('date')}** [{it.get('category')}]: {it.get('text')}")

        return "\n".join(output)

    def summarize(self, items: List[Dict[str, Any]], mode: str = "executive",
                  custom_question: Optional[str] = None, force_offline: bool = False,
                  timeframe_desc: str = "Selected Period") -> Dict[str, Any]:
        """
        Unified summarization dispatcher. Tries AI mode first unless forced offline,
        falling back to analytical summary on error.
        """
        if not items:
            return {
                "success": True,
                "engine": "none",
                "mode": mode,
                "summary": "No release notes available for the specified period/filters."
            }

        if not force_offline and self.agy_path:
            try:
                ai_summary = self.summarize_with_agy(items, mode=mode, custom_question=custom_question)
                return {
                    "success": True,
                    "engine": "agy-ai",
                    "mode": mode,
                    "summary": ai_summary
                }
            except Exception as e:
                print(f"[Warning] AI summarization failed ({e}), falling back to analytical summarizer...")

        # Fallback / Offline
        analytical_summary = self.summarize_analytical(items, timeframe_desc=timeframe_desc)
        return {
            "success": True,
            "engine": "analytical-rule-engine",
            "mode": mode,
            "summary": analytical_summary
        }


if __name__ == "__main__":
    from fetcher import ReleaseNotesFetcher

    fetcher = ReleaseNotesFetcher()
    items = fetcher.get_flat_items(days=14)
    print(f"Fetched {len(items)} items from last 14 days.")

    summarizer = ReleaseNotesSummarizer()
    print("\n--- Testing Analytical Summary ---")
    ana_res = summarizer.summarize(items, mode="digest", force_offline=True)
    print(ana_res["summary"][:400] + "...\n")

    print("--- Testing AI Executive Summary via agy ---")
    ai_res = summarizer.summarize(items, mode="executive")
    print(f"Engine used: {ai_res['engine']}")
    print(ai_res["summary"][:600] + "...")
