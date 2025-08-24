#!/usr/bin/env python3
"""
Enhanced Multi-Repository DEVLOG.md generator with simulated filter functionality.

This version creates a single Markdown file with:
1. Navigation buttons at the top
2. All commits section
3. Per-repository filtered sections
4. Collapsible sections for better organization
5. Interactive table of contents
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

# Repository configuration
REPOS = {
    "markdown-brain-bot": {
        "path": "/Users/colinaulds/Desktop/projects/markdown-brain-bot",
        "description": "Main backend system with Smart Rails routing",
        "github_url": "https://github.com/auldsyababua/markdown-brain-bot",
        "emoji": "🤖",
    },
    "gpt-parser": {
        "path": "/Users/colinaulds/Desktop/projects/gpt-parser",
        "description": "Early backend attempt with GPT parsing",
        "github_url": "https://github.com/auldsyababua/gpt-parser",
        "emoji": "🧠",
    },
    "bbui": {
        "path": "/Users/colinaulds/Desktop/projects/bbui",
        "description": "Frontend interface for FLRTS system",
        "github_url": "https://github.com/auldsyababua/bbui",
        "emoji": "🎨",
    },
}

# Try to load configuration from .devlog/config.json if it exists
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
config_file = os.path.join(project_root, ".devlog", "config.json")

if os.path.exists(config_file):
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
            if "repositories" in config:
                # Merge with default emojis
                for repo_name, repo_config in config["repositories"].items():
                    if repo_name in REPOS:
                        repo_config["emoji"] = REPOS[repo_name].get("emoji", "📦")
                REPOS = config["repositories"]
    except Exception as e:
        print(f"Warning: Could not load config from {config_file}: {e}")


def run_git_command(cmd: str, repo_path: str = None) -> str:
    """Run a git command and return output."""
    try:
        cwd = repo_path if repo_path else os.getcwd()
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True, cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if "--debug" in sys.argv:
            print(f"Git command failed: {cmd} (in {cwd})")
            print(f"Error: {e.stderr}")
        return ""


def get_commit_stats(commit_hash: str, repo_path: str) -> Dict:
    """Get file and line change statistics for a commit."""
    try:
        # Get the list of changed files with their change counts
        numstat_output = run_git_command(
            f'git show --numstat --format="" {commit_hash}', repo_path
        )

        files_changed = []
        total_insertions = 0
        total_deletions = 0

        for line in numstat_output.split("\n"):
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 3:
                    insertions = parts[0] if parts[0] != "-" else "0"
                    deletions = parts[1] if parts[1] != "-" else "0"
                    filename = "\t".join(parts[2:])

                    try:
                        ins_count = int(insertions) if insertions.isdigit() else 0
                        del_count = int(deletions) if deletions.isdigit() else 0

                        files_changed.append(
                            {
                                "filename": filename,
                                "insertions": ins_count,
                                "deletions": del_count,
                                "total_changes": ins_count + del_count,
                            }
                        )

                        total_insertions += ins_count
                        total_deletions += del_count
                    except ValueError:
                        files_changed.append(
                            {
                                "filename": filename,
                                "insertions": 0,
                                "deletions": 0,
                                "total_changes": 0,
                                "binary": True,
                            }
                        )

        return {
            "files_changed": len(files_changed),
            "files_list": files_changed,
            "total_insertions": total_insertions,
            "total_deletions": total_deletions,
            "total_changes": total_insertions + total_deletions,
        }

    except Exception as e:
        if "--debug" in sys.argv:
            print(f"Error getting stats for commit {commit_hash}: {e}")
        return {
            "files_changed": 0,
            "files_list": [],
            "total_insertions": 0,
            "total_deletions": 0,
            "total_changes": 0,
        }


def get_commit_info() -> List[Dict]:
    """Get detailed commit information from git log across all repositories."""
    all_commits = []

    for repo_name, repo_config in REPOS.items():
        if not os.path.exists(repo_config["path"]):
            if "--debug" in sys.argv:
                print(f"Warning: Repository path not found: {repo_config['path']}")
            continue

        try:
            # Get commit info
            log_output = run_git_command(
                'git log --pretty=format:"%H|%ad|%s|%an" --date=iso --reverse',
                repo_config["path"],
            )

            if not log_output:
                continue

            for line in log_output.split("\n"):
                if "|" in line:
                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        hash_full, date_str, subject, author = parts

                        try:
                            commit_date = datetime.fromisoformat(
                                date_str.replace(" -0700", "").replace(" -0800", "")
                            )
                        except ValueError:
                            commit_date = datetime.now()

                        stats = get_commit_stats(hash_full, repo_config["path"])

                        commit_info = {
                            "hash": hash_full,
                            "hash_short": hash_full[:7],
                            "date": commit_date,
                            "subject": subject,
                            "author": author,
                            "repo": repo_name,
                            "repo_description": repo_config["description"],
                            "github_url": repo_config["github_url"],
                            "emoji": repo_config.get("emoji", "📦"),
                            "stats": stats,
                        }

                        all_commits.append(commit_info)
        except Exception as e:
            if "--debug" in sys.argv:
                print(f"Error processing {repo_name}: {e}")
            continue

    all_commits.sort(key=lambda x: x["date"])
    return all_commits


def categorize_commit(subject: str) -> Tuple[str, str]:
    """Categorize commit by type."""
    subject_lower = subject.lower()

    if subject_lower.startswith("merge"):
        return "🟢", "PR merge"
    elif any(word in subject_lower for word in ["feat:", "feature:", "add "]):
        return "🟢", "Feature"
    elif any(word in subject_lower for word in ["fix:", "bug:"]):
        return "🟢", "Bug fix"
    elif any(word in subject_lower for word in ["docs:", "documentation"]):
        return "🟢", "Documentation"
    elif any(word in subject_lower for word in ["test:", "testing"]):
        return "🟢", "Testing"
    elif any(word in subject_lower for word in ["refactor:", "cleanup"]):
        return "🟢", "Refactor"
    elif any(word in subject_lower for word in ["wip:", "work in progress"]):
        return "🟡", "WIP"
    else:
        return "🟢", "Update"


def format_commit_entry(commit: Dict, show_repo_badge: bool = True) -> str:
    """Format a single commit entry."""
    repo_name = commit["repo"]
    repo_config = REPOS[repo_name]

    status_emoji, status_desc = categorize_commit(commit["subject"])

    # Repository badge
    if show_repo_badge:
        repo_badge = f"{commit['emoji']} **[{repo_name}]({repo_config['github_url']})** - {commit['repo_description']}"
    else:
        repo_badge = None

    # Format file changes
    stats = commit.get("stats", {})
    files_changed = stats.get("files_changed", 0)
    total_insertions = stats.get("total_insertions", 0)
    total_deletions = stats.get("total_deletions", 0)

    change_parts = []
    if total_insertions > 0:
        change_parts.append(f"+{total_insertions}")
    if total_deletions > 0:
        change_parts.append(f"-{total_deletions}")

    change_summary = " ".join(change_parts) if change_parts else "No changes"

    # Format files list (show up to 3 files for compact view)
    files_list = stats.get("files_list", [])
    files_display = []

    for i, file_info in enumerate(files_list):
        if i >= 3:
            remaining = len(files_list) - 3
            files_display.append(f"  - *...and {remaining} more files*")
            break

        filename = file_info["filename"]
        file_insertions = file_info.get("insertions", 0)
        file_deletions = file_info.get("deletions", 0)
        is_binary = file_info.get("binary", False)

        if is_binary:
            files_display.append(f"  - `{filename}` *(binary)*")
        else:
            file_change_parts = []
            if file_insertions > 0:
                file_change_parts.append(f"+{file_insertions}")
            if file_deletions > 0:
                file_change_parts.append(f"-{file_deletions}")
            file_changes = (
                " ".join(file_change_parts) if file_change_parts else "no changes"
            )
            files_display.append(f"  - `{filename}` ({file_changes})")

    files_section = (
        "\n".join(files_display) if files_display else "  - *No files modified*"
    )

    # Build commit entry
    entry = f"""### [{commit['hash_short']}] {commit['subject']}
"""

    if repo_badge:
        entry += f"- **Repository**: {repo_badge}\n"

    entry += f"""- **Date**: {commit['date'].strftime('%Y-%m-%d %H:%M:%S PST')}  
- **Author**: {commit['author']}
- **Status**: {status_emoji} {status_desc}
- **Changes**: {files_changed} files changed ({change_summary})
- **Commit**: [`{commit['hash_short']}`]({repo_config['github_url']}/commit/{commit['hash']})

<details>
<summary>Files Modified</summary>

{files_section}

</details>

"""

    return entry


def generate_navigation_bar() -> str:
    """Generate the navigation bar with filter buttons."""
    nav = """## 🔍 Quick Navigation

<div align="center">

### Filter by Repository

| [**📋 All Repositories**](#all-repositories) """

    # Add repository buttons
    for repo_name in REPOS.keys():
        emoji = REPOS[repo_name].get("emoji", "📦")
        # Create anchor-safe ID
        anchor_id = repo_name.lower().replace("-", "_")
        nav += f"| [**{emoji} {repo_name}**](#{anchor_id}_only) "

    nav += "|\n\n"

    # Add statistics and other links
    nav += """### Quick Links

| [**📊 Statistics**](#statistics) | [**📈 Repository Breakdown**](#repository-breakdown) | [**🗓️ Recent Activity**](#recent-activity) |

</div>

---
"""

    return nav


def generate_enhanced_devlog() -> str:
    """Generate the enhanced DEVLOG with filter functionality."""
    commits = get_commit_info()
    now = datetime.now()

    # Start with header
    devlog_content = f"""# Development Log - Multi-Repository View

> **Auto-Generated**: This file is programmatically updated from git history.  
> Last updated: {now.strftime('%Y-%m-%d at %H:%M:%S PST')}

{generate_navigation_bar()}

## Project Overview

This development log provides multiple views of your project's commit history:
- **All Repositories**: Complete chronological view across all repos
- **Per-Repository**: Filtered view showing only commits from specific repositories
- **Collapsible Sections**: Click on "Files Modified" to expand/collapse file details

### Repository Structure
"""

    # Add repository descriptions
    for repo_name, repo_config in REPOS.items():
        emoji = repo_config.get("emoji", "📦")
        devlog_content += f"- {emoji} **[{repo_name}]({repo_config['github_url']})**: {repo_config['description']}\n"

    devlog_content += "\n---\n\n"

    # Group commits by date and by repository
    commits_by_date = defaultdict(list)
    commits_by_repo = defaultdict(list)

    for commit in commits:
        date_key = commit["date"].strftime("%Y-%m-%d")
        commits_by_date[date_key].append(commit)
        commits_by_repo[commit["repo"]].append(commit)

    # Section 1: All Repositories View
    devlog_content += """<a name="all-repositories"></a>
## 📋 All Repositories

<a name="recent-activity"></a>
### Recent Activity

Showing all commits from all repositories in chronological order.

"""

    # Show last 10 days of activity
    dates_shown = 0
    for date_key in sorted(commits_by_date.keys(), reverse=True):
        if dates_shown >= 10:
            devlog_content += (
                "\n*For older commits, see the per-repository sections below.*\n\n"
            )
            break

        date_commits = commits_by_date[date_key]
        date_obj = datetime.strptime(date_key, "%Y-%m-%d")
        devlog_content += f"#### {date_obj.strftime('%Y-%m-%d')}\n\n"

        for commit in reversed(date_commits):
            devlog_content += format_commit_entry(commit, show_repo_badge=True)

        devlog_content += "---\n\n"
        dates_shown += 1

    # Section 2: Per-Repository Views
    devlog_content += """## 📁 Per-Repository Views

Click on any repository section below to see commits filtered by that repository only.

"""

    for repo_name in REPOS.keys():
        emoji = REPOS[repo_name].get("emoji", "📦")
        anchor_id = repo_name.lower().replace("-", "_")
        repo_commits = commits_by_repo.get(repo_name, [])

        devlog_content += f"""---

<a name="{anchor_id}_only"></a>
### {emoji} {repo_name} Repository Only

<details>
<summary>Click to expand {len(repo_commits)} commits from {repo_name}</summary>

"""

        # Group by date
        repo_dates = defaultdict(list)
        for commit in repo_commits:
            date_key = commit["date"].strftime("%Y-%m-%d")
            repo_dates[date_key].append(commit)

        # Show commits
        for date_key in sorted(repo_dates.keys(), reverse=True):
            date_commits = repo_dates[date_key]
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            devlog_content += f"\n#### {date_obj.strftime('%Y-%m-%d')}\n\n"

            for commit in reversed(date_commits):
                devlog_content += format_commit_entry(commit, show_repo_badge=False)

        devlog_content += "\n</details>\n\n"

    # Section 3: Statistics
    devlog_content += generate_statistics(commits, commits_by_repo)

    return devlog_content


def generate_statistics(
    commits: List[Dict], commits_by_repo: Dict[str, List[Dict]]
) -> str:
    """Generate statistics section."""
    total_commits = len(commits)
    unique_authors = len(set(commit["author"] for commit in commits))

    if commits:
        date_range = f"{commits[0]['date'].strftime('%B %d')}-{commits[-1]['date'].strftime('%d, %Y')}"
    else:
        date_range = "No commits found"

    # Calculate overall statistics
    total_files_changed = 0
    total_insertions = 0
    total_deletions = 0

    repo_stats = {}
    for repo_name, repo_commits in commits_by_repo.items():
        stats = {
            "commits": len(repo_commits),
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "authors": set(),
        }

        for commit in repo_commits:
            commit_stats = commit.get("stats", {})
            stats["files_changed"] += commit_stats.get("files_changed", 0)
            stats["insertions"] += commit_stats.get("total_insertions", 0)
            stats["deletions"] += commit_stats.get("total_deletions", 0)
            stats["authors"].add(commit["author"])

            total_files_changed += commit_stats.get("files_changed", 0)
            total_insertions += commit_stats.get("total_insertions", 0)
            total_deletions += commit_stats.get("total_deletions", 0)

        repo_stats[repo_name] = stats

    content = f"""---

<a name="statistics"></a>
## 📊 Statistics

### Overall Summary

| Metric | Value |
|--------|-------|
| **Total Commits** | {total_commits} |
| **Contributors** | {unique_authors} |
| **Files Changed** | {total_files_changed:,} |
| **Lines Added** | +{total_insertions:,} |
| **Lines Removed** | -{total_deletions:,} |
| **Net Change** | {total_insertions - total_deletions:+,} |
| **Development Period** | {date_range} |
| **Active Repositories** | {len(repo_stats)} |

<a name="repository-breakdown"></a>
### 📈 Repository Breakdown

| Repository | Commits | Contributors | Files Changed | Lines Changed |
|------------|---------|--------------|---------------|--------------|
"""

    # Sort by commit count
    for repo_name, stats in sorted(
        repo_stats.items(), key=lambda x: x[1]["commits"], reverse=True
    ):
        emoji = REPOS[repo_name].get("emoji", "📦")
        contributors = len(stats["authors"])
        line_changes = f"+{stats['insertions']:,} -{stats['deletions']:,}"

        content += f"| {emoji} **{repo_name}** | {stats['commits']} | {contributors} | {stats['files_changed']:,} | {line_changes} |\n"

    content += f"""

---

*This file is automatically generated from git history across all repositories.*  
*Use the navigation links at the top to filter by repository or jump to specific sections.*  
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S PST')}*
"""

    return content


def main():
    """Main function to generate enhanced DEVLOG."""
    parser = argparse.ArgumentParser(
        description="Generate enhanced multi-repository DEVLOG.md"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--output", default="DEVLOG.md", help="Output filename")
    args = parser.parse_args()

    print("Generating enhanced DEVLOG with navigation...")

    try:
        devlog_content = generate_enhanced_devlog()

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(devlog_content)

        print(f"✅ {args.output} generated successfully!")
        print("📊 Features included:")
        print("   - Navigation bar with repository filters")
        print("   - Collapsible sections for better organization")
        print("   - Per-repository filtered views")
        print("   - Enhanced statistics with tables")
        print("   - File change details in expandable sections")

    except Exception as e:
        print(f"❌ Error generating DEVLOG: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
