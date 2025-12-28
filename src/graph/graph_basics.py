# I model supply chain as directed, weighted graphs to indentify fragile nodes by
#  simulating failure and measuring how diruptions propogate through thr network.ex

import networkx as nx

def build_sample_graph():
    G = nx.DiGraph()

    G.add_edge("Suppliers_1", "Port_1", time = 4)
    G.add_edge("Port_1", "Port_2", time = 6)
    G.add_edge("Port_2", "Customer_1", time=5)

    return G

if __name__ == "__main__":
    G = build_sample_graph()
    print("Nodes:", G.nodes())
    print("Edges:", G.edges(data = True))
