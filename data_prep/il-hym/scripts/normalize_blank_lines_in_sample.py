#!/usr/bin/env python3
"""Normalize excessive blank lines in sampled files to max 1 blank line between paragraphs."""

from pathlib import Path
import re
import sys


def normalize_blank_lines(file_path: Path) -> int:
    """
    Clean up file formatting:
    1. Strip trailing whitespace from every line.
    2. Remove lines that become empty after stripping.
    3. Replace sequences of 2+ blank lines with a single blank line.
    
    Returns 1 if changes made, 0 otherwise.
    """
    text = file_path.read_text(encoding="utf-8")
    
    # Split into lines and process each one
    lines = text.split('\n')
    
    # Strip trailing whitespace from each line AND remove lines that become empty
    # (except we want to preserve intentional blank lines between paragraphs)
    cleaned_lines = []
    for line in lines:
        stripped = line.rstrip()
        # If line is not empty after stripping, keep it
        # If line is empty after stripping, we'll let collapse handle multiple blanks
        cleaned_lines.append(stripped)
    
    # Rejoin
    normalized = '\n'.join(cleaned_lines)
    
    # Collapse multiple consecutive blank lines to single blank line
    normalized = re.sub(r'\n\n\n+', '\n\n', normalized)
    
    if normalized != text:
        file_path.write_text(normalized, encoding="utf-8")
        return 1
    return 0


def main() -> None:
    sample_dir = Path(__file__).resolve().parent / "sample_600"
    
    if not sample_dir.exists():
        print(f"Error: {sample_dir} does not exist.")
        sys.exit(1)
    
    txt_files = sorted(sample_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {sample_dir}.")
        return
    
    normalized_count = 0
    
    for i, fpath in enumerate(txt_files, 1):
        try:
            if normalize_blank_lines(fpath):
                normalized_count += 1
                if i % 50 == 0 or normalized_count <= 10:
                    print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → normalized blank lines")
        except Exception as e:
            print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → ERROR: {e}")
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(txt_files)}")
    print(f"  Files with normalized blank lines: {normalized_count}")


if __name__ == "__main__":
    main()
