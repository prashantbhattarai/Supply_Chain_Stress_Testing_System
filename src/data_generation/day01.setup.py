# day 1 setup.py
import csv
import json

# function for loading Csv file

def load_csv(path):
    with open (path,"r") as f:
        return list(csv.DictReader(f))
    
# function to load the json files
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)
    
# funciton to make it only runs when the file is executed directly.
if __name__ == "__main__":
    print ("Day 1 setup completed.")
