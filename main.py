import collections
import enum
import time
import numpy.random as random
from logging_manager import logger
import gevent
import gevent.event
import gevent.pool
import gevent.queue
import gipc

from cycle_test_case import *

# должны быть глобальными из-за особенностей gipc с процессами и пайпами
pids = []
pipes_queue = gevent.queue.UnboundQueue()
procs_with_pipes = []


class WorkersManager:
    """
    Менеджер для воркеров, выполняющих CPU-bound задачи (каждый воркер это процесс)
    """

    def __init__(self, serialization_fun, deserialization_fun):
        self.serialization_fun = serialization_fun
        self.deserialization_fun = deserialization_fun

    def create_pool(self, count):
        for worker_num in range(count):
            one, two = gipc.pipe(True)
            proc = gipc.start_process(target=work, args=(calculate_flows, self.serialization_fun, one))
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


def work(task_function, serialize_function, pipe):
    """
    Функция, которая вызываются на процессах-воркерах.
    Должна быть вне класса, иначе появляются ошибки с references при gipc.start_process
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
        pipe.put(serialize_function(resp))
    pipe.close()


class AnnotatedFlow:
    """
    Аннотация для сущности потока для удобства вывода и работы с ними
    """

    def __init__(self, from_place, to_place):
        self.from_place = from_place
        self.to_place = to_place

    def __str__(self):
        return f"from {self.from_place} to {self.to_place}"


def serialize_flows(flows_to_pipe):
    flows_repr = []
    for i in flows_to_pipe:
        flows_repr.append((repr(i.from_place), repr(i.to_place)))
    return flows_repr


def deserialize_flows(flows_from_pipe):
    flows_eval = []
    for i in flows_from_pipe:
        flows_eval.append(AnnotatedFlow(eval(i[0]), eval(i[1])))
    return flows_eval


def calculate_flows(transition_repr, marking_repr):
    net.set_marking(eval(marking_repr))
    t = net.transition(eval(transition_repr))
    return [AnnotatedFlow(*t.flow(m)) for m in t.modes()]


def collect_flows(workers_manager_, transition, marking):
    return workers_manager_.process_task(repr(transition), repr(marking))


class ProcessorStates(enum.Enum):
    # TODO maybe rename statuses, maybe change logic
    STALE = 1
    ENQUEUED = 2
    TO_RETRY = 3


class SimulationManager:
    """
    Менеджер самой симуляции
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
        transitions_mapping = {t.name: TransitionProcessor(t.name, self, self.calculation_manager) for t in
                               net.transition()}

        for transition_name, transition in transitions_mapping.items():
            place_consuming_processors = set(trans for place in net.post(transition_name) for trans in net.post(place))
            for processor in place_consuming_processors:
                transition.consuming_processors.add(transitions_mapping[processor])

        # net.post(place.name) is a set itself and is not hashable, that is why frozenset
        grouped_by_place_transitions = set(frozenset(net.post(place.name)) for place in net.place())
        for place_transitions in grouped_by_place_transitions:
            transitions_processors = [transitions_mapping[t] for t in place_transitions]
            for cur_processor in transitions_processors:
                cur_processor.concurrent_processors.update(transitions_processors)

        for transition_processor in transitions_mapping.values():
            logger.debug(f"{transition_processor} <-- concurrent_processors: "
                          f"{'', ''.join(str(p.name) for p in transition_processor.concurrent_processors)}")
            logger.debug(f"{transition_processor} --> consuming_processors: "
                          f"{'', ''.join(str(p.name) for p in transition_processor.consuming_processors)}")
        return transitions_mapping.values()

    def startup(self, transitions):
        self.simulation_start = time.time()

        clients = gevent.pool.Group()
        # TODO add random?
        for t in transitions:
            t.state = ProcessorStates.ENQUEUED
            g = gevent.spawn(t.activate_transition)
            clients.add(g)
        clients.join()

    def print_stats(self):
        simulation_time = time.time() - self.simulation_start
        building_time = self.simulation_start - self.building_start
        logger.info(f"{len(pids)} workers, {building_time}s building overhead, "
                     f"{self.events_count} / {simulation_time} = {self.events_count / simulation_time} events per second")
        logger.info(f"Transition processors distribution: {self.events_distribution}")

    def update_marking(self, transition, moving_from_place, moving_to_place):
        new_marking = self.current_marking - moving_from_place + moving_to_place
        self.current_marking = new_marking
        logger.debug(f"[update_marking] {transition} \n"
                      f"\t before: {self.current_marking} \n"
                      f"\t after: {new_marking}")

        # Statistics updating
        self.events_count += 1
        self.events_distribution[transition] += 1


# TODO rename?
class TransitionProcessor:
    """
    Обработчики переходов, выполняются на greenlets, каждый обработчик закреплен за своим переходом
    """

    def __init__(self, name, simulation_manager, calculation_manager):
        self.calculation_manager = calculation_manager
        self.name = name
        self.simulation_manager = simulation_manager
        self.consuming_processors = set()
        self.concurrent_processors = set()
        self.state = ProcessorStates.STALE

    def __str__(self):
        return f"transition {self.name} processor"

    def activate_transition(self):
        greenlets = gevent.pool.Group()
        self.state = ProcessorStates.ENQUEUED

        logger.debug(f"{self}: COLLECTING FLOWS")
        marking = self.simulation_manager.current_marking
        collected_flows = collect_flows(self.calculation_manager, self.name, marking)

        flows = [f for f in collected_flows if f.from_place <= self.simulation_manager.current_marking]
        logger.debug(f"{self}: marking {marking} \n"
                      f"\t collected flows: {[str(f) for f in collected_flows]}\n"
                      f"\t available flows: {[str(f) for f in flows]}")

        # Got this state during collecting flows from other processor
        if len(flows) == 0 and self.state == ProcessorStates.TO_RETRY:
            logger.debug(f"{self}: RETRYING")
            g = gevent.spawn(self.activate_transition)
            greenlets.add(g)
        # Second part is redundant, for purpose of demonstrating state changes
        elif len(flows) == 0 and self.state == ProcessorStates.ENQUEUED:
            logger.debug(f"{self}: STALE")
            self.state = ProcessorStates.STALE
        else:
            flow = random.choice(flows)
            logger.debug(f"{self} chosen flow {flow}")
            self.simulation_manager.update_marking(self.name, flow.from_place, flow.to_place)
            self.state = ProcessorStates.STALE
            # TODO add random?
            for player in self.concurrent_processors | self.consuming_processors:
                if player.state == ProcessorStates.STALE:
                    logger.debug(f"{self} => enqueue {player.name}")
                    player.state = ProcessorStates.ENQUEUED
                    g = gevent.spawn(player.activate_transition)
                    greenlets.add(g)
                elif player.state == ProcessorStates.ENQUEUED:
                    if player in self.consuming_processors:
                        logger.debug(f"{self} => to retry {player.name}")
                        player.state = ProcessorStates.TO_RETRY
        gevent.joinall(greenlets)


if __name__ == "__main__":
    workers_manager = WorkersManager(serialize_flows, deserialize_flows)
    workers_manager.create_pool(10)
    # timeout = 5
    manager = SimulationManager(workers_manager, net)
    try:
        transition_processors = manager.build()
        logger.debug("start simulation for %r" % net.name)
        manager.startup(transition_processors)
        # if timeout:
        #     gevent.sleep(timeout)
        #     manager.print_stats()
        #     workers_manager.destroy_pool()
        #     sys.exit(0)
    except KeyboardInterrupt:
        manager.print_stats()
        workers_manager.destroy_pool()
        sys.exit(0)
