import random


def generate_formula(variables, length):
    # Generating binary tree like formula with atomic constraints as leaves
    if length % 2 != 0 or length < 2:
        raise ValueError("Length must be an even integer greater than or equal to 2.")
    k = length // 2
    return _generate_subformula(k, variables)


def _generate_subformula(k, variables):
    if k == 1:
        # "Leaf" atomic constraint
        var1 = random.choice(variables)
        var2 = random.choice(variables)
        op = random.choice(['◁', '~◁'])
        return f"{var1} {op} {var2}"
    else:
        # Split into two parts and combine with ∧ or ∨
        k1 = random.randint(1, k - 1)
        k2 = k - k1
        left = _generate_subformula(k1, variables)
        right = _generate_subformula(k2, variables)
        op = random.choice(['∨', '∧'])
        return f"({left}) {op} ({right})"
