#!/usr/bin/env python3

import sys
import os
import re

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <filename>")
    sys.exit(1)

filename = sys.argv[1]

if not os.path.isfile(filename):
    print(f"'{filename}' is NOT a file.")
    sys.exit(1)

def process_line(line):
    # Convert leading tabs to 4 spaces
    leading = re.match(r'^(\s*)', line)
    if leading:
        leading_whitespace = leading.group(1)
        # Replace tabs with 4 spaces
        converted = leading_whitespace.replace('\t', ' ' * 4)
        num_spaces = len(converted)
    else:
        num_spaces = 0

    # Replace only the leading whitespace
    stripped_line = re.sub(r'^\s*', converted, line)

    # Check pattern
    pattern = r"^\s*/\*\*\s+@brief"
    match = re.search(pattern, stripped_line)

    return num_spaces, bool(match)

def split_at_first_whitespace(s):
    parts = re.split(r'\s+', s, maxsplit=1)
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]

pattern1 = r"^\s*\**\s*@.*\s" #(param|retval|note|return)"
pattern2 = r"^\s*\*/"
indent = 0

with open(filename, "r") as file:
    lines = file.readlines()
with open(filename, "w") as file:
    for line in lines:
        # Get indent to @brief comment
        spaces, matched = process_line(line)
        if matched:
            indent = spaces
            a = line.split("@", 1)[1]
            keyword, remain = split_at_first_whitespace(a)
            spaces = 7 - len(keyword)
            file.write(f"{' ' * indent}/** @{keyword}{' ' * spaces}{remain}")
        elif re.search(pattern1, line):
            a = line.split("@", 1)[1]
            keyword, remain = split_at_first_whitespace(a)
            spaces = 7 - len(keyword)
            file.write(f"{' ' * indent}    @{keyword}{' ' * spaces}{remain}")
        elif re.search(pattern2, line):
            remain = line.strip()
            file.write(f"{' ' * indent}{remain}\n")
        else:
            file.write(line)

