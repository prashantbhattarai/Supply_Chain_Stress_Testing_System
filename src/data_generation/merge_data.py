"""Join supplier attributes to outgoing routes without import-time work."""
from src.data_generation.suppliers import generate_suppliers
from src.data_generation.routes import generate_routes


def merge_supplier_routes(suppliers, routes):
    """Keep every supplier, repeating its attributes for each outgoing route."""
    return suppliers.merge(routes, left_on="supplier_id", right_on="origin", how="left", validate="one_to_many")


if __name__ == "__main__":
    print(merge_supplier_routes(generate_suppliers(10, seed=42), generate_routes(10, end=10, seed=42)))
