from snakes.nets import *


class Cycle:
    def __init__(self, tokens, length):
        self.tokens = tokens
        self.length = length
        self.net = PetriNet("cycle_net")

    def build(self):
        for i in range(self.length):
            p = Place(f"p[{i}]", [dot] if i < self.tokens else [])
            t = Transition(f"t[{i}]")
            self.net.add_place(p)
            self.net.add_transition(t)

        for i in range(self.length):
            self.net.add_input(f"p[{i}]", f"t[{i}]", Value(dot))
            self.net.add_output(f"p[{(i+1) % self.length}]", f"t[{i}]", Value(dot))


model = Cycle(length=10, tokens=4)
model.build()
net = model.net
