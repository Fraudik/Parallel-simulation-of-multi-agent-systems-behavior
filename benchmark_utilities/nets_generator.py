import random
import sys
from math import ceil

import matplotlib.pyplot as plt
import networkx as nx
import snakes.nets as snakes

from config import IS_DEBUG


class NetsGenerator:
    def __init__(self, tokens, length, edge_density, nets_amount=1):
        self.nets_amount = nets_amount
        self.tokens = tokens
        self.length = length
        self.edge_density = edge_density
        self.nets = snakes.PetriNet("generated_net")

        self.places = []
        self.transitions = []
        self.edges = []

    def build(self):
        self.places = []
        for i in range(self.length):
            self.places.append(f"p[{i}]")

        transition_count = 0
        net_length = ceil(self.length / self.nets_amount)
        possible_edges = net_length * net_length
        edge_count = int(possible_edges * self.edge_density)
        added_places = []
        # generate edges only inside one net
        for idx in range(0, self.length, net_length):
            component_edges = []

            numbers = list(range(idx, idx + net_length))
            for _ in range(edge_count):
                transition_count += 1
                t = snakes.Transition(f"t[{transition_count}]")
                self.nets.add_transition(t)
                self.transitions.append(f"t[{transition_count}]")

                i, j = random.choice(numbers), random.choice(numbers)
                component_edges.append(("in", f"p[{i}]", f"t[{transition_count}]"))
                component_edges.append(("out", f"p[{j}]", f"t[{transition_count}]"))

            cur_tokens_amount = 0
            for edge in component_edges:
                if edge[1] not in added_places:
                    if cur_tokens_amount < self.tokens:
                        cur_tokens_amount += 1
                        p = snakes.Place(edge[1], [snakes.dot])
                    else:
                        p = snakes.Place(edge[1])
                    self.nets.add_place(p)
                    added_places.append(edge[1])

                if edge[0] == 'in':
                    self.nets.add_input(edge[1], edge[2], snakes.Value(snakes.dot))
                elif edge[0] == 'out':
                    self.nets.add_output(edge[1], edge[2], snakes.Value(snakes.dot))
            self.edges += component_edges

        # Removing places without edges
        self.places = added_places.copy()

    def draw(self):
        G = nx.DiGraph()

        for place in self.places:
            G.add_node(place, type='place')
        for transition in self.transitions:
            G.add_node(transition, type='transition')
        for edge in self.edges:
            if edge[0] == 'in':
                G.add_edge(edge[1], edge[2], type='input')
            elif edge[0] == 'out':
                G.add_edge(edge[2], edge[1], type='output')

        pos = nx.spring_layout(G, seed=42)
        plt.figure(figsize=(10, 8))
        places = [node for node, attr in G.nodes(data=True) if attr['type'] == 'place']
        transitions = [node for node, attr in G.nodes(data=True) if attr['type'] == 'transition']

        # green transitions, blue places
        nx.draw_networkx_nodes(G, pos, places, node_size=500, node_color='lightblue', label="Place")
        nx.draw_networkx_nodes(G, pos, transitions, node_size=500, node_color='lightgreen', label="Transition")

        edges = G.edges()
        nx.draw_networkx_edges(G, pos, edgelist=edges, edge_color='black', width=2, alpha=0.5)
        nx.draw_networkx_labels(G, pos, font_size=12, font_color='black')

        plt.title("Petri Net Visualization")
        plt.axis('off')
        plt.show()


def save_to_file(net, filename):
    pnml_string = snakes.dumps(net)
    with open(filename, 'w') as f:
        f.write(pnml_string)


def load_from_file(filename):
    with open(filename, 'r') as f:
        pnml_string = f.read()
    return snakes.loads(pnml_string)


if __name__ == "__main__":
    nets_generator = NetsGenerator(tokens=int(sys.argv[1]), length=int(sys.argv[2]),
                                   edge_density=float(sys.argv[3]), nets_amount=int(sys.argv[4]))
    nets_generator.build()
    if IS_DEBUG:
        nets_generator.draw()
    save_to_file(nets_generator.nets, f'nets.pnml')
