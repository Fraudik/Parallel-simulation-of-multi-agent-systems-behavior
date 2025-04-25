import collections
import enum
import gc
import time
import numpy.random as random

from base_baseline_algorithn import run_baseline_simulation
from ipc_utilities import AnnotatedMovement, work, deserialize_base_movements, serialize_base_movements, \
    request_base_movement_calculation
from logging_manager import logger
import gevent
import gevent.event
import gevent.pool
import gevent.queue
import gipc

from snakes.nets import *
from nets_generator import *

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
            resp = self.deserialization_fun(pipe.get())
        except:
            return []
        pipes_queue.put(pipe)
        if isinstance(resp, Exception):
            return []
        else:
            return resp


def calculate_movement(transition_repr, marking_repr):
    net.set_marking(eval(marking_repr))
    t = net.transition(eval(transition_repr))
    # there is maximum only one movement can be available for basic Petri Net,
    # but SNAKES library is made for different sorts of Petri nets with possibly many movements and thus return list
    return [AnnotatedMovement(*t.flow(m)) for m in t.modes()]


class HandlerStates(enum.Enum):
    STALE = 1
    ENQUEUED = 2
    TO_RETRY = 3


class SimulationManager:
    """
    Simulation manager starts simulation and keeps all the common data for transitions handlers
    """

    def __init__(self, calculation_manager, net_):
        self.current_marking = net_.get_marking()
        self.calculation_manager = calculation_manager

        # Statistics info
        self.events_count = 0
        self.events_distribution = collections.defaultdict(int)
        self.building_start = time.time()
        self.simulation_start = None

    def build(self):
        transitions_mapping = {t.name: TransitionHandler(t.name, self, self.calculation_manager) for t in
                               net.transition()}

        for transition_name, transition in transitions_mapping.items():
            place_consuming_handlers = set(trans for place in net.post(transition_name) for trans in net.post(place))
            for handler in place_consuming_handlers:
                transition.consuming_handlers.add(transitions_mapping[handler])

        # net.post(place.name) is a set itself and is not hashable, that is why frozenset
        grouped_by_place_transitions = set(frozenset(net.post(place.name)) for place in net.place())
        for place_transitions in grouped_by_place_transitions:
            transitions_handlers = [transitions_mapping[t] for t in place_transitions]
            for cur_handler in transitions_handlers:
                cur_handler.concurrent_handlers.update(transitions_handlers)

        for transition_handler in transitions_mapping.values():
            logger.debug(f"{transition_handler} <-- concurrent_handlers: "
                         f"{'', ''.join(str(p.name) for p in transition_handler.concurrent_handlers)}")
            logger.debug(f"{transition_handler} --> consuming_handlers: "
                         f"{'', ''.join(str(p.name) for p in transition_handler.consuming_handlers)}")
        return transitions_mapping.values()

    def startup(self, transitions):
        self.simulation_start = time.time()

        handlers_coroutines = gevent.pool.Group()
        # no need to shuffle them, as we enqueue each handler exactly one time
        for t in transitions:
            t.state = HandlerStates.ENQUEUED
            g = gevent.spawn(t.activate_transition)
            handlers_coroutines.add(g)
        handlers_coroutines.join()

    def print_stats(self):
        simulation_time = time.time() - self.simulation_start
        building_time = self.simulation_start - self.building_start
        logger.info(f"{len(pids)} workers, {building_time}s building overhead, "
                    f"{self.events_count} / {simulation_time} = {self.events_count / simulation_time} events per second")
        logger.info(f"Transition handlers distribution: {self.events_distribution}")

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
        calculated_movement = request_base_movement_calculation(self.calculation_manager,
                                                                self.name,
                                                                self.simulation_manager.current_marking)
        can_perform_movement = self._check_movement(calculated_movement)
        logger.debug(f"{self}: marking {self.simulation_manager.current_marking} \n"
                     f"\t calculated movement: {calculated_movement}\n"
                     f"\t it is available: {can_perform_movement}")

        if not can_perform_movement and self.state == HandlerStates.TO_RETRY:
            logger.debug(f"{self}: RETRYING")
            g = gevent.spawn(self.activate_transition)
            coroutines_to_enqueue.add(g)
        elif not can_perform_movement:
            logger.debug(f"{self}: STALE")
            self.state = HandlerStates.STALE
        else:
            self.state = HandlerStates.STALE
            # here name passed for logging and statistics purposes only
            self.simulation_manager.perform_movement(self.name, calculated_movement)

            # shuffle for purposes of fairness
            # Python set can not be shuffled and also is not purely random shuffled itself
            other_handlers = list(self.concurrent_handlers.union(self.consuming_handlers))
            random.shuffle(other_handlers)
            for other_handler in other_handlers:
                if other_handler.state == HandlerStates.STALE:
                    logger.debug(f"{self} => enqueue {other_handler.name}")
                    other_handler.state = HandlerStates.ENQUEUED
                    g = gevent.spawn(other_handler.activate_transition)
                    coroutines_to_enqueue.add(g)
                elif other_handler.state == HandlerStates.ENQUEUED:
                    if other_handler in self.consuming_handlers:
                        logger.debug(f"{self} => to retry {other_handler.name}")
                        other_handler.state = HandlerStates.TO_RETRY
        gevent.joinall(coroutines_to_enqueue)


if __name__ == "__main__":
    pids = []
    pipes_queue = gevent.queue.UnboundQueue()
    procs_with_pipes = []
    timeout = 5
    compare_with_baseline_algorithm = False

    workers_manager = WorkersManager(serialize_base_movements, deserialize_base_movements)
    workers_manager.create_pool(10)
    manager = SimulationManager(workers_manager, net)
    gevent_timeout = gevent.Timeout(timeout)
    gevent_timeout.start()
    try:
        transition_processors = manager.build()
        logger.debug("start simulation for %r" % net.name)
        manager.startup(transition_processors)
    finally:
        class DevNull:
            def write(self, msg):
                pass

        manager.print_stats()
        # manager.print_stats_for_benchmarks()
        # Suppressing errors from interrupted greenlets, because with gracefully shutdown they do not stop
        sys.stderr = DevNull()
        gevent.killall(
            [obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet)]
        )
        workers_manager.destroy_pool()

        if compare_with_baseline_algorithm:
            run_baseline_simulation(timeout=timeout)

        sys.exit(0)
