import numpy as np

np.random.seed(42)

def generate_lead_times(mean = 10, std = 3, size = 1000):
    return np.random.normal(loc = mean , scale = std, size = size)

def apply_global_disruption(times, shock_factor = 1.2): 
    return times * shock_factor

if __name__ == "main":
    lead_times = generate_lead_times()
    disrupted = apply_global_disruption(lead_times)
    print("Sample orginal lead times:", lead_times)
    print("Sample disrupted lead_times:", disrupted[:5])
    print("Mean Increase:", disrupted.mean()- lead_times.mean())


""" # this code simulates delivery time in supply chain 
and I generate lead times in it that varies around the average
 value so that it mimic the real world data, random.seed is used to 
 ensure that the random numbers results are same every time so that 
 testing can be authentic"""
