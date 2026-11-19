"""Small standard-library file readers shared by the setup examples."""
import csv
import json


def load_csv(path):
    """Read a CSV file as a list of dictionaries using its header row."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path):
    """Read a UTF-8 JSON file as Python objects."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
