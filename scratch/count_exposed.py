import sys

# Count exposed methods in order
with open('06_notes/athlete_base_methods_table.txt') as f:
    lines = f.readlines()

# Let's check where the exposed tags are in the XMLs that correspond to these methods
print("Total base methods in table:", len(lines))
