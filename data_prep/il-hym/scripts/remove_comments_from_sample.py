#!/usr/bin/env python3
"""Remove user comment blocks from sampled files, keeping only article content."""

from pathlib import Path
import sys


def clean_file(file_path: Path) -> tuple[int, str]:
    """
    Remove comment blocks from a file.
    
    Returns (lines_removed, status_message).
    Comment blocks are identified by the pattern:
      # userid_hash = ...
      # commentid = ...
      # parent_commentid = ...
      # likes = ...
      # dislikes = ...
    
    We find the first occurrence of this pattern AFTER publication_date and truncate there.
    """
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    
    # Find publication_date line
    pub_date_idx = None
    for i, line in enumerate(lines):
        if line.startswith("# publication_date ="):
            pub_date_idx = i
            break
    
    if pub_date_idx is None:
        return 0, "no_pub_date"
    
    # Search for first comment block starting AFTER publication_date
    # A comment block is identified by a sequence of 5 lines:
    # # userid_hash = ...
    # # commentid = ...
    # # parent_commentid = ...
    # # likes = ...
    # # dislikes = ...
    
    first_comment_idx = None
    for i in range(pub_date_idx + 1, len(lines) - 4):
        if (lines[i].startswith("# userid_hash =") and
            lines[i + 1].startswith("# commentid =") and
            lines[i + 2].startswith("# parent_commentid =") and
            lines[i + 3].startswith("# likes =") and
            lines[i + 4].startswith("# dislikes =")):
            first_comment_idx = i
            break
    
    if first_comment_idx is None:
        return 0, "no_comments"
    
    # Truncate at the first comment block
    cleaned_lines = lines[:first_comment_idx]
    
    # Remove trailing blank lines before comments
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()
    
    # Write back
    cleaned_text = "".join(cleaned_lines)
    file_path.write_text(cleaned_text, encoding="utf-8")
    
    lines_removed = len(lines) - len(cleaned_lines)
    return lines_removed, "cleaned"


def main() -> None:
    sample_dir = Path(__file__).resolve().parent / "sample_600"
    
    if not sample_dir.exists():
        print(f"Error: {sample_dir} does not exist.")
        sys.exit(1)
    
    txt_files = sorted(sample_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {sample_dir}.")
        return
    
    stats = {"cleaned": 0, "no_comments": 0, "no_pub_date": 0, "error": 0}
    total_lines_removed = 0
    
    for i, fpath in enumerate(txt_files, 1):
        try:
            lines_removed, status = clean_file(fpath)
            stats[status] += 1
            total_lines_removed += lines_removed
            
            if status == "cleaned":
                print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → removed {lines_removed:4d} lines")
            elif status == "no_comments":
                if i % 50 == 0:
                    print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → no comments")
        except Exception as e:
            stats["error"] += 1
            print(f"[{i}/{len(txt_files)}] {fpath.name:40s} → ERROR: {e}")
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(txt_files)}")
    print(f"  Files cleaned: {stats['cleaned']}")
    print(f"  Files with no comments: {stats['no_comments']}")
    print(f"  Files with no pub_date: {stats['no_pub_date']}")
    print(f"  Files with errors: {stats['error']}")
    print(f"  Total lines removed: {total_lines_removed}")


if __name__ == "__main__":
    main()
