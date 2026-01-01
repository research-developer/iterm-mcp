#!/usr/bin/env python3
"""
Apply Changelog Notes Script

This script manages changelog entries for git commits. It can:
1. Attach changelog entries to commits using git notes
2. Generate a consolidated CHANGELOG.md from all entries
3. Optionally rewrite commit messages (requires force push)

Usage:
    python apply_changelog_notes.py notes          # Add git notes to commits
    python apply_changelog_notes.py changelog      # Generate CHANGELOG.md
    python apply_changelog_notes.py --rewrite      # Rewrite commit messages (DANGEROUS)
    python apply_changelog_notes.py all            # Add notes + generate changelog
"""

import argparse
import subprocess
import sys
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

# Import our changelog entries
try:
    from changelog_entries import (
        CHANGELOG_ENTRIES,
        VERSION_MAPPING,
        SKIPPED_COMMITS,
        get_entries_by_type,
        get_breaking_changes
    )
except ImportError:
    print("Error: changelog_entries.py not found in current directory")
    sys.exit(1)


def run_git_command(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        check=False
    )
    if check and result.returncode != 0:
        print(f"Git command failed: git {' '.join(args)}")
        print(f"Error: {result.stderr}")
    return result


def format_changelog_entry(entry: Dict) -> str:
    """Format a single changelog entry for git notes or display."""
    lines = []
    lines.append(f"## Changelog Entry")
    lines.append(f"")
    lines.append(f"**Type:** {entry['type']}")
    lines.append(f"**Date:** {entry['date']}")
    if entry.get('breaking'):
        lines.append(f"**Breaking Change:** Yes")
    if entry.get('pr_number'):
        lines.append(f"**PR:** #{entry['pr_number']}")
    lines.append(f"")
    lines.append(f"### Changes:")
    for change in entry['entries']:
        lines.append(f"- {change}")
    return "\n".join(lines)


def add_git_notes(dry_run: bool = False) -> int:
    """Add git notes to commits with changelog entries."""
    print("Adding git notes to commits with changelog entries...")
    success_count = 0
    error_count = 0

    for commit_hash, entry in CHANGELOG_ENTRIES.items():
        note_content = format_changelog_entry(entry)

        if dry_run:
            print(f"\n[DRY RUN] Would add note to {commit_hash}:")
            print(note_content)
            success_count += 1
            continue

        # Remove existing note if present (to allow updates)
        run_git_command(["notes", "remove", commit_hash], check=False)

        # Add the new note
        result = subprocess.run(
            ["git", "notes", "add", "-m", note_content, commit_hash],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"  Added note to {commit_hash}: {entry['title'][:50]}...")
            success_count += 1
        else:
            print(f"  Failed to add note to {commit_hash}: {result.stderr}")
            error_count += 1

    print(f"\nCompleted: {success_count} notes added, {error_count} errors")
    return error_count


def generate_changelog(output_file: str = "CHANGELOG.md") -> None:
    """Generate a consolidated CHANGELOG.md from all entries."""
    print(f"Generating {output_file}...")

    # Group entries by version
    version_entries: Dict[str, List[tuple]] = defaultdict(list)

    for commit_hash, entry in CHANGELOG_ENTRIES.items():
        # Find which version this commit belongs to
        version = "Unreleased"
        for ver, ver_data in VERSION_MAPPING.items():
            if commit_hash in ver_data.get("commits", []):
                version = ver
                break
        version_entries[version].append((commit_hash, entry))

    # Sort entries within each version by date (newest first)
    for version in version_entries:
        version_entries[version].sort(key=lambda x: x[1]['date'], reverse=True)

    # Define version order
    version_order = ["Unreleased"] + [v for v in VERSION_MAPPING.keys() if v != "Unreleased"]

    # Build the changelog content
    lines = []
    lines.append("# Changelog")
    lines.append("")
    lines.append("All notable changes to the iTerm MCP Server will be documented in this file.")
    lines.append("")
    lines.append("The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),")
    lines.append("and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).")
    lines.append("")

    for version in version_order:
        if version not in version_entries:
            continue

        entries = version_entries[version]
        if not entries:
            continue

        # Get date range for this version
        dates = [e[1]['date'] for e in entries]
        latest_date = max(dates)

        if version == "Unreleased":
            lines.append(f"## [Unreleased]")
        else:
            lines.append(f"## [{version}] - {latest_date}")
        lines.append("")

        # Group by change type
        type_groups: Dict[str, List[str]] = defaultdict(list)
        breaking_changes = []

        for commit_hash, entry in entries:
            change_type = entry['type']
            for change in entry['entries']:
                # Add commit reference
                change_with_ref = f"{change} ([{commit_hash[:7]}](../../commit/{commit_hash}))"
                type_groups[change_type].append(change_with_ref)

                if entry.get('breaking'):
                    breaking_changes.append(change_with_ref)

        # Output in standard order: Added, Changed, Deprecated, Removed, Fixed, Security
        type_order = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

        # Add breaking changes section if any
        if breaking_changes:
            lines.append("### BREAKING CHANGES")
            for change in breaking_changes:
                lines.append(f"- {change}")
            lines.append("")

        for change_type in type_order:
            if change_type in type_groups:
                lines.append(f"### {change_type}")
                for change in type_groups[change_type]:
                    lines.append(f"- {change}")
                lines.append("")

    # Write to file
    content = "\n".join(lines)
    with open(output_file, 'w') as f:
        f.write(content)

    print(f"Generated {output_file} with {len(CHANGELOG_ENTRIES)} entries across {len(version_entries)} versions")


def rewrite_commit_messages(dry_run: bool = True) -> None:
    """
    Rewrite commit messages to include changelog entries.

    WARNING: This rewrites git history and requires a force push.
    Only use on branches that aren't shared with others.
    """
    if not dry_run:
        print("=" * 60)
        print("WARNING: This will rewrite git history!")
        print("You will need to force push after this operation.")
        print("This can cause issues for anyone who has pulled this branch.")
        print("=" * 60)
        confirm = input("Type 'REWRITE' to confirm: ")
        if confirm != "REWRITE":
            print("Aborted.")
            return

    print("Rewriting commit messages..." if not dry_run else "[DRY RUN] Would rewrite commit messages...")

    # Get all commits in order (oldest first for rebase)
    result = run_git_command(["log", "--format=%H", "--reverse", "06ce8b0..HEAD"])
    if result.returncode != 0:
        print("Failed to get commit list")
        return

    commits = result.stdout.strip().split("\n")
    rewrite_count = 0

    for commit_hash in commits:
        if commit_hash not in CHANGELOG_ENTRIES:
            continue

        entry = CHANGELOG_ENTRIES[commit_hash]

        # Get current commit message
        result = run_git_command(["log", "-1", "--format=%B", commit_hash])
        if result.returncode != 0:
            continue

        current_msg = result.stdout.strip()

        # Build new message with changelog footer
        changelog_footer = f"\n\n---\nChangelog: {entry['type']}\n"
        for change in entry['entries']:
            changelog_footer += f"- {change}\n"
        if entry.get('breaking'):
            changelog_footer += "BREAKING CHANGE: Yes\n"

        new_msg = current_msg + changelog_footer

        if dry_run:
            print(f"\n[DRY RUN] Would update {commit_hash[:7]}:")
            print(f"  Current: {current_msg[:50]}...")
            print(f"  Would add changelog footer")
            rewrite_count += 1
        else:
            # This would use git filter-branch or git-filter-repo
            # For safety, we'll just print instructions
            print(f"Would rewrite {commit_hash[:7]}")
            rewrite_count += 1

    if dry_run:
        print(f"\n[DRY RUN] Would rewrite {rewrite_count} commit messages")
        print("Run with --rewrite --force to actually perform the rewrite")
    else:
        print(f"\nTo actually rewrite commits, use git-filter-repo or interactive rebase")
        print("This script generates the changelog entries; manual rebase is recommended")


def list_notes() -> None:
    """List all commits that have changelog notes attached."""
    print("Commits with changelog notes:")
    print("-" * 60)

    result = run_git_command(["notes", "list"])
    if result.returncode != 0 or not result.stdout.strip():
        print("No notes found. Run 'python apply_changelog_notes.py notes' to add them.")
        return

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            note_hash, commit_hash = parts[0], parts[1]
            # Get commit message
            msg_result = run_git_command(["log", "-1", "--format=%s", commit_hash])
            if msg_result.returncode == 0:
                print(f"  {commit_hash[:7]}: {msg_result.stdout.strip()[:50]}")


def show_note(commit_hash: str) -> None:
    """Show the changelog note for a specific commit."""
    result = run_git_command(["notes", "show", commit_hash])
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"No note found for commit {commit_hash}")


def show_stats() -> None:
    """Show statistics about the changelog entries."""
    print("Changelog Entry Statistics")
    print("=" * 40)
    print(f"Total entries: {len(CHANGELOG_ENTRIES)}")
    print(f"Skipped commits: {len(SKIPPED_COMMITS)}")
    print()

    # Count by type
    type_counts = defaultdict(int)
    for entry in CHANGELOG_ENTRIES.values():
        type_counts[entry['type']] += 1

    print("By type:")
    for change_type in ["Added", "Changed", "Fixed", "Removed", "Deprecated", "Security"]:
        if change_type in type_counts:
            print(f"  {change_type}: {type_counts[change_type]}")

    print()

    # Count by version
    print("By version:")
    for version, ver_data in VERSION_MAPPING.items():
        commits = ver_data.get("commits", [])
        count = len([c for c in commits if c in CHANGELOG_ENTRIES])
        print(f"  {version}: {count} entries")

    # Breaking changes
    breaking = get_breaking_changes()
    print(f"\nBreaking changes: {len(breaking)}")
    for commit_hash, entry in breaking.items():
        print(f"  {commit_hash[:7]}: {entry['title'][:50]}")


def main():
    parser = argparse.ArgumentParser(
        description="Apply changelog entries to git commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python apply_changelog_notes.py notes        Add git notes to all changelog commits
  python apply_changelog_notes.py changelog    Generate CHANGELOG.md
  python apply_changelog_notes.py all          Add notes and generate changelog
  python apply_changelog_notes.py stats        Show changelog statistics
  python apply_changelog_notes.py list         List commits with notes
  python apply_changelog_notes.py show abc123  Show note for specific commit
        """
    )

    parser.add_argument(
        "command",
        choices=["notes", "changelog", "all", "stats", "list", "show", "rewrite"],
        help="Command to execute"
    )

    parser.add_argument(
        "commit",
        nargs="?",
        help="Commit hash (for 'show' command)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--output", "-o",
        default="CHANGELOG.md",
        help="Output file for changelog (default: CHANGELOG.md)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force dangerous operations (required for --rewrite)"
    )

    args = parser.parse_args()

    if args.command == "notes":
        add_git_notes(dry_run=args.dry_run)

    elif args.command == "changelog":
        generate_changelog(output_file=args.output)

    elif args.command == "all":
        add_git_notes(dry_run=args.dry_run)
        print()
        generate_changelog(output_file=args.output)

    elif args.command == "stats":
        show_stats()

    elif args.command == "list":
        list_notes()

    elif args.command == "show":
        if not args.commit:
            print("Error: 'show' command requires a commit hash")
            sys.exit(1)
        show_note(args.commit)

    elif args.command == "rewrite":
        if args.force:
            rewrite_commit_messages(dry_run=False)
        else:
            rewrite_commit_messages(dry_run=True)
            print("\nUse --force to actually rewrite (DANGEROUS)")


if __name__ == "__main__":
    main()
