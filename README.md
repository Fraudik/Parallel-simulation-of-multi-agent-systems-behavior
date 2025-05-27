# Parallel simulation of multi-agent systems behavior

An algorithm employing non-blocking synchronization through utilisation of coroutines implemented as part of a research project. \
It is based on the open-source SNAKES for the possibility of further modification and use by other researchers or developers.

# Project structure
Greenlet from the **gevent** was chosen as the implementation of the coroutine mechanism. **gipc**, specially developed for **gevent**, was chosen for interprocessor interaction and the allocation of individual processes for calculations.\
The project uses the **uv** package manager.

The logic related to the algorithm is located in the base\_proposed\_algorithm and workflow\_proposed\_algorithm files for regular Petri nets and workflow networks, respectively.
The algorithm itself is in the activate\_transition function of the TransitionHandler class.

A specialized Timeout class from the **gevent** is used to interrupt and terminate coroutines upon reaching a specified simulation time.

SimulationHandler is responsible for initialization, that is, the initial preparation for launching the simulation. The same class stores common variables used by handlers during the simulation process and simulation statistics. Currently, these statistics include the number of events that occurred during the simulation; the time spent on initialization and the entire simulation process; and the distribution of activations by transitions.

The work with processes for calculations, as well as interprocess communication, is located in the ipc\_utilities file. The WorkersManager class is responsible for managing the processes allocated for calculations. It creates a channel for each process and creates a queue with channels. At the end of the simulation, this same class terminates the processes and closes the channels. During initialization, the class accepts a function for calculating threads, as well as functions for serializing and deserializing its input and output data. Thus, this code can be easily reused for other subtypes of Petri nets, while leaving it isolated from their specific logic.

The constraint\_evaluation file contains the rules for the lexer, parser, and calculation of the abstract syntax tree (AST) for the interface formula. The **Lark** is used for this. The syntax for writing the formula is described there.
