import collections
import enum
import gc
import time

import gevent
import gevent.event
import gevent.pool
import gevent.queue
import gipc
import numpy.random as random

from constraint_generator import generate_formula
from constraints_evaluation import CheckActivationValidity, constraint_parser
from ipc_utilities import AnnotatedMovement, serialize_base_movements, deserialize_base_movements, work, \
    request_workflow_movement_calculation, serialize_workflow_movements, deserialize_workflow_movements
from logging_manager import logger
from nets_generator import *

from snakes.nets import *

from workflow_baseline_algorithm import run_baseline_simulation

# net is loaded globally to make it available for all processes, and it costs to load it on every calculation
net = load_from_file('nets.pnml')


class WorkersManager:
    """
    Workers manager for performing CPU-bound tasks (each worker is a process)
    """

    def __init__(self, serialization_fun, deserialization_fun):
        self.serialization_fun = serialization_fun
        self.deserialization_fun = deserialization_fun

    def create_pool(self, count):
        for worker_num in range(count):
            one, two = gipc.pipe(True)
            proc = gipc.start_process(target=work, args=(calculate_movement, self.serialization_fun, one))
            pids.append(proc.pid)
            pipes_queue.put(two)
            procs_with_pipes.append((proc, two))

    def destroy_pool(self):
        for proc, pipe in procs_with_pipes:
            try:
                pipe.close()
            except:
                pass
            try:
                proc.terminate()
            except:
                pass

    def process_task(self, *args, **kwargs):
        pipe = pipes_queue.get()
        try:
            pipe.put((args, kwargs))
        except:
            return []
        try:
            resp = self.deserialization_fun(*pipe.get())
        except:
            return []
        pipes_queue.put(pipe)
        if isinstance(resp, Exception):
            return []
        else:
            return resp


def calculate_movement(transition_repr, marking_repr, trace, constraint_formula_):
    # TODO add docstring

    net.set_marking(eval(marking_repr))
    t = net.transition(eval(transition_repr))
    # TODO - possible optimization is to check available movement before calling calculate movement
    movements = [AnnotatedMovement(*t.flow(m)) for m in t.modes()]
    if not movements:
        return [], [], []

    # We need to check only for occurrence of specific names in the trace, can use set for O(1) search
    validator = CheckActivationValidity(set(trace), t.name)
    tree = constraint_parser.parse(constraint_formula_)
    is_valid_to_fire = validator.transform(tree)
    if not is_valid_to_fire:
        return [], [], []

    return movements, validator.possibly_enabled_transitions, validator.possibly_disabled_transitions


class HandlerStates(enum.Enum):
    STALE = 1
    ENQUEUED = 2
    POSSIBLY_ENABLED = 3
    POSSIBLY_DISABLED = 4


class SimulationManager:
    """
    Simulation manager starts simulation and keeps all the common data for transitions handlers
    """

    def __init__(self, calculation_manager, net_, constraint_formula_):
        self.current_marking = net_.get_marking()
        self.calculation_manager = calculation_manager
        self.constraint_formula = constraint_formula_

        # mapping transition names to their handlers, added this logic for passing possibly_enabled/disabled
        self.transitions_mapping = {}
        self.trace = []

        # Statistics info
        self.events_count = 0
        self.events_distribution = collections.defaultdict(int)
        self.building_start = time.time()
        self.simulation_start = None

    def build(self):
        self.transitions_mapping = {t.name: TransitionHandler(t.name, self, self.calculation_manager) for t in
                                    net.transition()}

        for transition_name, transition in self.transitions_mapping.items():
            place_consuming_handlers = set(trans for place in net.post(transition_name) for trans in net.post(place))
            for handler in place_consuming_handlers:
                transition.consuming_handlers.add(handler)

        # net.post(place.name) is a set itself and is not hashable, that is why frozenset
        grouped_by_place_transitions = set(frozenset(net.post(place.name)) for place in net.place())
        for place_transitions in grouped_by_place_transitions:
            transitions_handlers = [t for t in place_transitions]
            for cur_handler in transitions_handlers:
                self.transitions_mapping[cur_handler].concurrent_handlers.update(transitions_handlers)

        for transition_handler in self.transitions_mapping.values():
            logger.debug(f"{transition_handler} <-- concurrent_handlers: "
                         f"{', '.join(str(p) for p in transition_handler.concurrent_handlers)}")
            logger.debug(f"{transition_handler} --> consuming_handlers: "
                         f"{', '.join(str(p) for p in transition_handler.consuming_handlers)}")
        return self.transitions_mapping.values()

    def startup(self, transitions):
        self.simulation_start = time.time()

        handlers_coroutines = gevent.pool.Group()
        # TODO add random?
        for t in transitions:
            t.state = HandlerStates.ENQUEUED
            g = gevent.spawn(t.activate_transition)
            handlers_coroutines.add(g)
        handlers_coroutines.join()

    def print_stats(self):
        simulation_time = time.time() - self.simulation_start
        building_time = self.simulation_start - self.building_start
        logger.info(f"Constraint formula: {self.constraint_formula}")
        logger.info(f"Simulation trace: {self.trace}")
        logger.info(f"{len(pids)} workers, {building_time}s building overhead, "
                    f"{self.events_count} / {simulation_time} = {self.events_count / simulation_time} events per second")
        logger.info(f"Transition handlers distribution: {self.events_distribution}")
        return self.events_count / simulation_time

    def print_stats_for_benchmarks(self):
        simulation_time = time.time() - self.simulation_start
        logger.info(f"{self.events_count / simulation_time}")
        return self.events_count / simulation_time

    def perform_movement(self, transition_name, movement: AnnotatedMovement):
        new_marking = self.current_marking - movement.start_places + movement.end_places
        logger.debug(f"[perform_movement] {transition_name} \n"
                     f"\t before: {self.current_marking} \n"
                     f"\t after: {new_marking}")
        self.current_marking = new_marking
        self.trace.append(transition_name)

        # Statistics updating
        self.events_count += 1
        self.events_distribution[transition_name] += 1


class TransitionHandler:
    """
    Transition handlers, executed on couroutines (greenlets), each handler is assigned to a different transition
    """

    def __init__(self, name, simulation_manager, calculation_manager):
        self.name = name
        self.calculation_manager = calculation_manager
        self.simulation_manager = simulation_manager

        self.consuming_handlers = set()
        self.concurrent_handlers = set()
        self.state = HandlerStates.STALE

    def __str__(self):
        return f"transition {self.name} handler"

    def _check_movement(self, movement: AnnotatedMovement):
        if movement is None:
            return False
        if movement.start_places <= self.simulation_manager.current_marking:
            return True
        return False

    def activate_transition(self):
        coroutines_to_enqueue = gevent.pool.Group()
        self.state = HandlerStates.ENQUEUED

        logger.debug(f"{self}: CALCULATING MOVEMENT")
        calculated_movement, possibly_enabled, possible_disabled = request_workflow_movement_calculation(self.calculation_manager,
                                                                             self.name,
                                                                             self.simulation_manager.current_marking,
                                                                             self.simulation_manager.trace,
                                                                             self.simulation_manager.constraint_formula)
        can_perform_movement = self._check_movement(calculated_movement)
        logger.debug(f"{self}: marking {self.simulation_manager.current_marking} \n"
                     f"\t calculated movement: {calculated_movement}\n"
                     f"\t it is available: {can_perform_movement}")
        if ((self.state == HandlerStates.POSSIBLY_DISABLED) or
                (not can_perform_movement and self.state == HandlerStates.POSSIBLY_ENABLED)):
            logger.debug(f"{self}: possibly disabled, retrying")
            cor = gevent.spawn(self.activate_transition)
            coroutines_to_enqueue.add(cor)
        elif not can_perform_movement:
            logger.debug(f"{self}: stale")
            self.state = HandlerStates.STALE
        else:
            self.state = HandlerStates.STALE
            self.simulation_manager.perform_movement(self.name, calculated_movement)

            # shuffle for purposes of fairness
            # Python set can not be shuffled and also is not purely random shuffled itself
            other_handlers = list(self.concurrent_handlers | self.consuming_handlers | set(possibly_enabled))
            random.shuffle(other_handlers)
            for handler_name in other_handlers:
                handler = self.simulation_manager.transitions_mapping[handler_name]
                if handler.state == HandlerStates.STALE:
                    logger.debug(f"{self} => enqueue {handler.name}")
                    handler.state = HandlerStates.ENQUEUED
                    cor = gevent.spawn(handler.activate_transition)
                    coroutines_to_enqueue.add(cor)
                elif handler_name not in self.concurrent_handlers and handler.state == HandlerStates.ENQUEUED:
                    logger.debug(f"{self} => possibly enabled {handler.name}")
                    handler.state = HandlerStates.POSSIBLY_ENABLED

            # this separate cycle does not affect fairness, as it does not queue coroutines
            for handler_name in possible_disabled:
                handler = self.simulation_manager.transitions_mapping[handler_name]
                if handler.state == HandlerStates.ENQUEUED:
                    logger.debug(f"{self} => possibly disabled {handler.name}")
                    handler.state = HandlerStates.POSSIBLY_DISABLED

        gevent.joinall(coroutines_to_enqueue)


if __name__ == "__main__":
    # должны быть глобальными из-за особенностей gipc с процессами и пайпами
    pids = []
    pipes_queue = gevent.queue.UnboundQueue()
    procs_with_pipes = []
    timeout = 3
    compare_with_baseline_algorithm = True

    variables = [t for t in net.transition()]
    length = int(sys.argv[1])
    constraint_formula = generate_formula(variables, length)

    workers_manager = WorkersManager(serialize_workflow_movements, deserialize_workflow_movements)
    workers_manager.create_pool(10)
    manager = SimulationManager(workers_manager, net, constraint_formula)
    gevent_timeout = gevent.Timeout(timeout)
    gevent_timeout.start()
    try:
        transition_handlers = manager.build()
        logger.debug("start simulation for %r" % net.name)
        manager.startup(transition_handlers)
    finally:
        class DevNull:
            def write(self, msg):
                pass


        # manager.print_stats()
        manager.print_stats_for_benchmarks()
        # Suppressing errors from interrupted greenlets, because with gracefully shutdown they do not stop
        sys.stderr = DevNull()
        gevent.killall(
            [obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet)]
        )
        workers_manager.destroy_pool()

        if compare_with_baseline_algorithm:
            run_baseline_simulation(constraint_formula=constraint_formula, timeout=timeout)

        sys.exit(0)
