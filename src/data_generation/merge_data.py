""" This code combines mulitple datasets from the previous works and then
produce the single ready dataset for analysis
"""
from src.data_generation.suppliers import generate_suppliers
from src.data_generation.routes import generate_routes

import pandas as pd

suppliers = generate_suppliers(10)
routes = generate_routes(10)

merged = suppliers.merge(routes, left_on= "supplier_id",right_on="origin", how= "left")
print("Merged DataSet:\n", merged)

# how="left" keeps all rows from the left DataFrame and 
# fills missing matches from the right with NaN.