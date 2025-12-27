# day01_setup.py
import csv
import json

def load_csv(path):
    with open(path, 'r') as f:
        return list(csv.DictReader(f))

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

# Step 4: Run this when the file is executed directly
if __name__ == "__main__":
    print("Day 1 setup complete.")
