#!/usr/bin/env python3
"""Clean up lines with excessive internal spacing by collapsing multiple spaces to single space."""

from pathlib import Path
import re
import sys


def clean_file(file_path: Path) -> int:
    """
    For each line, collapse multiple consecutive spaces to single space.
    
    Returns 1 if changes made, 0 otherwise.
    """
    text = file_path.read_text(encoding="utf-8")
    
    # Replace 2+ consecutive spaces with single space
    # This handles both regular spaces and other whitespace
    normalized = re.sub(r' {2,}', ' ', text)
    
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
                if i % 50 == 1 or cleaned_count <= 20:
                    print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → collapsed internal spaces")
        except Exception as e:
            print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → ERROR: {e}")
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(txt_files)}")
    print(f"  Files with collapsed spaces: {cleaned_count}")


if __name__ == "__main__":
    main()
