from lark import Transformer, v_args, Lark

constraint_grammar = """
    ?start: logic_formula?

    ?logic_formula: constraint
        | logic_formula "∨" logic_formula  -> or_
        | logic_formula "∧" logic_formula  -> and_
        | "(" logic_formula ")"

    ?constraint: NAME "◁" NAME  -> precedes
        | NAME "~◁" NAME  -> not_precedes

    NAME: /[A-Za-z0-9]+((\[?)(_?)(\-?)(\d*)(\]?))/
    %import common.WS_INLINE
    
    %ignore WS_INLINE
""" # noqa W605


@v_args(inline=True)
class CheckActivationValidity(Transformer):
    # TODO annotate
    def __init__(self, trace_to_check, transition_to_fire):
        super().__init__()
        self.trace_to_check = trace_to_check
        self.transition_name = transition_to_fire
        self.possibly_enabled_transitions = []
        self.possibly_disabled_transitions = []

    def and_(self, x, y):
        return x and y

    def or_(self, x, y):
        return x or y

    def not_precedes(self, preceding, succeeding):
        if preceding == self.transition_name:
            self.possibly_disabled_transitions.append(str(succeeding))
        if succeeding != self.transition_name:
            return True
        return preceding not in self.trace_to_check

    def precedes(self, preceding, succeeding):
        if preceding == self.transition_name:
            self.possibly_enabled_transitions.append(str(succeeding))
        if succeeding != self.transition_name:
            return True
        return preceding in self.trace_to_check


constraint_parser = Lark(constraint_grammar, parser='lalr')
