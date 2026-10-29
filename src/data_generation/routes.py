"""Generate directed transportation routes between integer supplier IDs."""
import numpy as np
import pandas as pd


def generate_routes(n=100, start=1, end=20, seed=None):
    """Return n routes within inclusive start..end, with transit times in hours.

    The first route connects start to end when n > 0. Self-routes are avoided.
    Repeated pairs are allowed; build_graph keeps their fastest transit time.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)):
        raise ValueError("start and end must be integers")
    if start >= end:
        raise ValueError("start must be less than end")
    rng = np.random.default_rng(seed)
    origins = rng.integers(start, end + 1, size=n)
    # Choose from all other IDs by shifting offsets around the origin.
    destinations = start + (origins - start + rng.integers(1, end - start + 1, size=n)) % (end - start + 1)
    if n > 0:
        origins[0], destinations[0] = start, end
    return pd.DataFrame({
        "route_id": range(1, n + 1),
        "origin": origins,
        "destination": destinations,
        "time": rng.integers(2, 15, size=n),
    })


if __name__ == "__main__":
    print(generate_routes(10, seed=42))
