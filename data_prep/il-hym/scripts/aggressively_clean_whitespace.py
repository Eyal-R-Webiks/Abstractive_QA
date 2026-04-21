#!/usr/bin/env python3
"""Aggressively clean whitespace-only lines and normalize blank lines."""

from pathlib import Path
import sys


def clean_file(file_path: Path) -> int:
    """
    Remove whitespace-only lines and normalize excessive blank lines.
    
    Returns 1 if changes made, 0 otherwise.
    """
    text = file_path.read_text(encoding="utf-8")
    lines = text.split('\n')
    
    # Step 1: Remove lines that contain ONLY whitespace (but keep truly empty lines)
    # A truly empty line is len 0, anything else is len > 0
    # We want to remove lines where .strip() is empty (only whitespace)
    # but keep lines that already are empty strings
    preserved = []
    for line in lines:
        # If the line, when stripped, is empty, skip it
        # This removes both truly empty lines AND whitespace-only lines
        if line.strip():
            preserved.append(line)
        else:
            # Only add blank line if the previous line wasn't already blank
            # This prevents consecutive blanks
            if not preserved or preserved[-1].strip():
                preserved.append("")
    
    normalized = '\n'.join(preserved)
    
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
    
    cleaned_count = 0
    
    for i, fpath in enumerate(txt_files, 1):
        try:
            if clean_file(fpath):
                cleaned_count += 1
                if cleaned_count <= 20 or i % 100 == 0:
                    print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → cleaned")
        except Exception as e:
            print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → ERROR: {e}")
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(txt_files)}")
    print(f"  Files cleaned: {cleaned_count}")


if __name__ == "__main__":
    main()
