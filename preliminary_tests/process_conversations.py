#!/usr/bin/env python3
"""
Process conversation JSON file:
1. Preserve the original file structure and content
2. Add split turn_2 prompt fields for entries based on turn_1_preference category
3. For "שתיהן טובות", use weighted random selection with even distribution
"""

import json
import random
from collections import defaultdict
from pathlib import Path


def set_split_prompt_fields(entry_data, model_response):
    """Populate the split turn_2 prompt fields on an entry."""
    entry_data.pop("turn_2_prompt_for_ls", None)
    entry_data["turn_2_prompt_for_ls_user1"] = entry_data.get("turn_1_user_prompt", "")
    entry_data["turn_2_prompt_for_ls_model"] = model_response
    entry_data["turn_2_prompt_for_ls_user2"] = entry_data.get("turn_2_user_prompt", "")


def process_conversations(input_file, output_file):
    """Process conversation file according to specifications."""
    
    # Load data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} entries")
    
    # Separate entries by preference category (keeping original structure)
    bad_entries = []
    both_good_entries = []
    pref_a_entries = []
    pref_b_entries = []
    
    for i, entry in enumerate(data):
        # Extract the data object (nested structure)
        entry_data = entry.get("data", {})
        pref = entry_data.get("turn_1_preference", "").strip()
        
        # Store both the full entry (with wrapper) and the inner data for processing
        if pref == "שתיהן גרועות":
            bad_entries.append((i, entry))
        elif pref == "שתיהן טובות":
            both_good_entries.append((i, entry))
        elif pref in ["A הרבה יותר טובה", "A מעט יותר טובה"]:
            pref_a_entries.append((i, entry))
        elif pref in ["B הרבה יותר טובה", "B מעט יותר טובה"]:
            pref_b_entries.append((i, entry))
    
    print(f"  - שתיהן גרועות: {len(bad_entries)}")
    print(f"  - שתיהן טובות: {len(both_good_entries)}")
    print(f"  - A preference: {len(pref_a_entries)}")
    print(f"  - B preference: {len(pref_b_entries)}")
    
    print(f"\nPreserving all original entries: {len(data)} entries remain")
    
    # Process "שתיהן טובות" entries with weighted distribution
    print("\nProcessing 'שתיהן טובות' entries with weighted random distribution...")
    
    # Build model distribution map
    model_a_counts = defaultdict(int)
    model_b_counts = defaultdict(int)
    model_selection_count = defaultdict(int)
    response_selection_count = {"a": 0, "b": 0}
    
    for idx, entry in both_good_entries:
        entry_data = entry.get("data", {})
        model_a = entry_data.get("turn_1_model_id_a", "unknown")
        model_b = entry_data.get("turn_1_model_id_b", "unknown")
        model_a_counts[model_a] += 1
        model_b_counts[model_b] += 1
    
    # Randomized order for processing (to avoid bias in early selections)
    indices = list(range(len(both_good_entries)))
    random.shuffle(indices)
    
    for idx in indices:
        entry_idx, entry = both_good_entries[idx]
        entry_data = entry.get("data", {})
        model_a = entry_data.get("turn_1_model_id_a", "unknown")
        model_b = entry_data.get("turn_1_model_id_b", "unknown")
        
        # Calculate weights based on how many times each has been selected
        weight_a = 1.0 / (model_selection_count[model_a] + response_selection_count["a"] + 1)
        weight_b = 1.0 / (model_selection_count[model_b] + response_selection_count["b"] + 1)
        
        # Weighted random choice
        total_weight = weight_a + weight_b
        if random.random() < weight_a / total_weight:
            selected_response = entry_data.get("turn_1_response_a", "")
            selected_model = model_a
            response_choice = "a"
        else:
            selected_response = entry_data.get("turn_1_response_b", "")
            selected_model = model_b
            response_choice = "b"
        
        # Update counters
        model_selection_count[selected_model] += 1
        response_selection_count[response_choice] += 1
        
        set_split_prompt_fields(entry_data, selected_response)
    
    print(f"  Selection distribution (both_good):")
    print(f"    - Response A: {response_selection_count['a']}")
    print(f"    - Response B: {response_selection_count['b']}")
    print(f"  Model selection counts:")
    for model, count in sorted(model_selection_count.items(), key=lambda x: -x[1]):
        print(f"    - {model}: {count}")
    
    # Process "A preference" entries
    print(f"\nProcessing {len(pref_a_entries)} 'A preference' entries...")
    for entry_idx, entry in pref_a_entries:
        entry_data = entry.get("data", {})
        set_split_prompt_fields(entry_data, entry_data.get("turn_1_response_a", ""))
    
    # Process "B preference" entries
    print(f"Processing {len(pref_b_entries)} 'B preference' entries...")
    for entry_idx, entry in pref_b_entries:
        entry_data = entry.get("data", {})
        set_split_prompt_fields(entry_data, entry_data.get("turn_1_response_b", ""))
    
    # Keep the original structure and entry order intact.
    all_processed = data
    
    # Save to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_processed, f, ensure_ascii=False, indent=2)
    
    print(f"\nProcessing complete!")
    print(f"Output file: {output_file}")
    print(f"Total entries written: {len(all_processed)}")
    entries_with_split_fields = sum(
        1
        for entry in all_processed
        if all(
            field in entry.get("data", {})
            for field in (
                "turn_2_prompt_for_ls_user1",
                "turn_2_prompt_for_ls_model",
                "turn_2_prompt_for_ls_user2",
            )
        )
    )
    print(f"  - With split LS prompt fields: {entries_with_split_fields}")


if __name__ == "__main__":
    input_path = Path("/Users/eyalrosenstein/Documents/Abstractive_QA/PLExp/sandbox/conversation_round1_turn2_pilot100.json")
    output_path = Path("/Users/eyalrosenstein/Documents/Abstractive_QA/PLExp/sandbox/conversation_round1_turn2_pilot100_split_prompts.json")
    
    process_conversations(input_path, output_path)
