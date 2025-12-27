import pandas as pd
import numpy as np

np.random.seed(42)

def generate_routes(n = 100):
    return pd.DataFrame({
        "route_id" : range( 1, n+1),
        "origin" : np.random.randint(1, 20 , size = n),
        "destination": np.random.randint(1,20, size = n),
        "time": np.random.randint(2, 15, size = n)

    })
# test 
routes_df= generate_routes(10)
print(routes_df)
# this file is just generating data for the transportation routes, , we use randomseed here so that it starts with the same randomness
# then I generate datas for  id, origin, destination and timing for the process.
