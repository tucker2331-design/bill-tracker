import re

# Our exact Lexicon from the master build
LOCAL_LEXICON = {
    "House General Laws": ["general laws"], 
    "House Finance": ["finance"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"]
}

IGNORE_WORDS = {"committee", "on", "the", "of", "and", "for", "meeting", "joint", "to", "referred", "assigned", "re-referred"}

def test_delta_check(chamber_prefix, raw_csv_string):
    outcome_lower = raw_csv_string.lower()
    
    # 1. Standard Lexicon Match
    matched_committee = None
    for api_name, aliases in LOCAL_LEXICON.items():
        if api_name.startswith(chamber_prefix):
            for alias in aliases:
                if alias in outcome_lower:
                    matched_committee = api_name
                    break
        if matched_committee: break

    if not matched_committee:
        return f"⚠️ [Unmapped] No Lexicon Match for: {raw_csv_string}"

    # 2. The Delta Check (Zero Data Loss Protocol)
    # Extract only the destination part of the string
    target_string = outcome_lower
    for verb in ["referred to ", "assigned to ", "re-referred to "]:
        if verb in target_string:
            target_string = target_string.split(verb)[-1]
            break

    # Convert strings to sets of words, stripping punctuation
    original_words = set(re.findall(r'\b\w+\b', target_string))
    lexicon_words = set(re.findall(r'\b\w+\b', matched_committee.lower()))
    
    # What is left over after we remove the Lexicon words AND the safe Noise words?
    leftover_words = original_words - lexicon_words - IGNORE_WORDS

    if leftover_words:
        return f"⚠️ [Unmapped Sub-Entity] {raw_csv_string} \n   -> (Blocked from becoming '{matched_committee}' because of leftovers: {leftover_words})"
    else:
        return f"✅ [SAFE MERGE] '{raw_csv_string}' -> perfectly maps to '{matched_committee}'"


# --- THE STRESS TEST BATCH ---
test_cases = [
    ("House ", "Referred to the Committee on General Laws"),             # Standard (Should Pass)
    ("Senate ", "Re-referred to Finance and Appropriations"),            # Standard (Should Pass)
    ("House ", "Referred to Finance"),                                   # Standard short-hand (Should Pass)
    ("House ", "Assigned to Finance - Subgrp A"),                        # Weird Sub (Should FAIL & Flag)
    ("Senate ", "Referred to Courts of Justice (Criminal Workgroup)"),   # Weird Sub (Should FAIL & Flag)
    ("Senate ", "Referred to Finance Committee"),                        # Standard with "Committee" (Should Pass)
]

print("🧪 RUNNING ISOLATED DELTA CHECK STRESS TEST...\n")
for chamber, text in test_cases:
    result = test_delta_check(chamber, text)
    print(result)
    print("-" * 60)
