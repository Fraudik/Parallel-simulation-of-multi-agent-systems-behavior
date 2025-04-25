import typing

from snakes.nets import *


def work(task_function, serialize_function, pipe):
    """
    A function that is called to request calculations from workers.
    Must be outside the class, otherwise errors with references to appear at gipc.start_process
    """
    while True:
        try:
            l, k = pipe.get()
        except EOFError:
            break
        try:
            resp = task_function(*l, **k)
        except Exception as exc:
            resp = exc
        pipe.put(serialize_function(*resp))
    pipe.close()


class AnnotatedMovement:
    """
    Annotation for movements for ease of working with it and logging
    """

    def __init__(self, start_places, end_places):
        self.start_places = start_places
        self.end_places = end_places

    def __str__(self):
        return f"from {self.start_places} to {self.end_places}"


def serialize_base_movements(movements_to_pipe: typing.List[AnnotatedMovement]):
    movements_repr = []
    for i in movements_to_pipe:
        movements_repr.append((repr(i.start_places), repr(i.end_places)))
    return movements_repr


def deserialize_base_movements(movements_from_pipe: typing.List[str]):
    movements_eval = []
    for i in movements_from_pipe:
        movements_eval.append(AnnotatedMovement(eval(i[0]), eval(i[1])))
    return movements_eval


def request_base_movement_calculation(workers_manager_, transition, marking):
    # SNAKES library is made for different sorts of Petri nets with possibly many movements and thus return list
    movements = workers_manager_.process_task(repr(transition), repr(marking))
    if len(movements) == 0:
        return None
    return movements[0]


def serialize_workflow_movements(movements_to_pipe: typing.List[AnnotatedMovement],
                                 possibly_enabled_transitions, possibly_disabled_transitions):
    movements_repr = []
    for i in movements_to_pipe:
        movements_repr.append((repr(i.start_places), repr(i.end_places)))
    return movements_repr, possibly_enabled_transitions, possibly_disabled_transitions


def deserialize_workflow_movements(movements_from_pipe: typing.List[str],
                                   possibly_enabled_transitions, possibly_disabled_transitions):
    movements_eval = []
    for i in movements_from_pipe:
        movements_eval.append(AnnotatedMovement(eval(i[0]), eval(i[1])))
    return movements_eval, possibly_enabled_transitions, possibly_disabled_transitions


def request_workflow_movement_calculation(workers_manager_, transition, marking, trace, constraint_formula_):
    # SNAKES library is made for different sorts of Petri nets with possibly many movements and thus return list
    movements, possibly_enabled, possible_disabled = workers_manager_.process_task(repr(transition), repr(marking),
                                                                                   trace, constraint_formula_)
    if len(movements) == 0:
        # in this case these two lists should be empty, as check for possible movement is done before filling them
        return None, possibly_enabled, possible_disabled
    return movements[0], possibly_enabled, possible_disabled
