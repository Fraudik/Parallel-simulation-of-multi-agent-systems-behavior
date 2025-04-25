import time

from constraints_evaluation import CheckActivationValidity, constraint_parser
from ipc_utilities import AnnotatedMovement
from nets_generator import load_from_file


def run_baseline_simulation(constraint_formula: str, timeout: int):
    net = load_from_file('nets.pnml')

    def _calculate_movement(_transition):
        movements = [AnnotatedMovement(*_transition.flow(m)) for m in _transition.modes()]
        if len(movements) == 0:
            return None

        # We need to check only for occurrence of specific names in the trace, can use set for O(1) search
        validator = CheckActivationValidity(set(trace), _transition.name)
        tree = constraint_parser.parse(constraint_formula)
        is_valid_to_fire = validator.transform(tree)
        if not is_valid_to_fire:
            return None

        return movements[0]

    def _check_movement(_current_marking, movement):
        if movement is None:
            return False
        if movement.start_places <= _current_marking:
            return True
        return False

    events_amount = 0
    simulation_start = time.time()
    trace = []
    current_marking = net.get_marking()
    while time.time() - simulation_start < timeout:
        for transition in net.transition():
            calculated_movement = _calculate_movement(transition)
            can_perform_movement = _check_movement(current_marking, calculated_movement)
            if can_perform_movement:
                new_marking = current_marking - calculated_movement.start_places + calculated_movement.end_places
                current_marking = new_marking
                trace.append(transition.name)
                events_amount += 1
                break
    simulation_end = time.time()
    # generally it is used for benchmarks only
    # TODO path to global
    with open('benchs/data/experiment_baseline.txt', 'a') as f:
        f.write(f'{events_amount / (simulation_end - simulation_start)}\n')
