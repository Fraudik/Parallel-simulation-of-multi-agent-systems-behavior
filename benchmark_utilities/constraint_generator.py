import random


def generate_formula(variables, length):
    """ Generating formula as binary tree with atomic constraints as leaves """
    if length % 2 != 0 or length < 2:
        raise ValueError("Length must be an even integer greater than or equal to 2.")
    tree_size = length // 2
    return generate_subformula(tree_size, variables)


def generate_subformula(k, variables):
    """ Generating subformula """
    if k == 1:
        first_name = random.choice(variables)
        second_name = random.choice(variables)
        op = random.choice(['◁', '~◁'])
        return f"{first_name} {op} {second_name}"
    else:
        left_subtree_size = random.randint(1, k - 1)
        right_subtree_size = k - left_subtree_size
        left = generate_subformula(left_subtree_size, variables)
        right = generate_subformula(right_subtree_size, variables)
        op = random.choice(['∨', '∧'])
        return f"({left}) {op} ({right})"
