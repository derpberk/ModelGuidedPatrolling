import sys
sys.path.append('.')

from PathPlanners.NRRA import WanderingAgent
from deap import algorithms
from deap import base
from deap import creator
from deap import tools
import multiprocessing as mp
import deap
import signal

import matplotlib.pyplot as plt

import numpy as np
from Environment.PatrollingEnvironment import DiscreteModelBasedPatrolling
from deap.algorithms import eaMuPlusLambda

import pickle

def init_pool():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

""" Create an environment """

nav_map = np.genfromtxt('Environment\Maps\map.txt', delimiter=' ')
N = 4

initial_positions = np.array([[42,32],
                            [50,40],
                            [43,44],
                            [35,45]])

env = DiscreteModelBasedPatrolling(n_agents=N,
								navigation_map=nav_map,
								initial_positions=initial_positions,
								model_based=True,
								movement_length=2,
								resolution=1,
								influence_radius=2,
								forgetting_factor=2,
								max_distance=300,
								benchmark='shekel',
								dynamic=False,
								reward_weights=[1.0, 1.0],
								reward_type='local_changes',
								model='miopic',
								seed=5000,
                                random_gt=False)

""" Create a genetic algorithm """

iteration = 0
seed = 0


# Create a fitness function
def fitness_function(individual):

    # Transform the individual numpy array into a TxN array of actions
    individual = np.array(individual).reshape(-1,N)

    # Reset the environment

    W_mean = []
    I_mean = []

    for _ in range(1):

        env.reset()

        # Run the environment
        W = 0.0
        I = 0.0

        for t in range(individual.shape[0]):
            # Get the actions of the agents at time t
            actions = {i:individual[t,i] for i in range(N)}

            # Step the environment
            _, _, _, info = env.step(actions)

            W += info['W']
            I += info['I']

        W_mean.append(W.copy())
        I_mean.append(I.copy())

    # Set the seed to an arbitrary value

    return np.mean(W_mean), np.mean(I_mean)

def cxTwoPointCopy(ind1, ind2):

    size = len(ind1)
    cxpoint1 = np.random.randint(1, size)
    cxpoint2 = np.random.randint(1, size - 1)
    if cxpoint2 >= cxpoint1:
        cxpoint2 += 1
    else: # Swap the two cx points
        cxpoint1, cxpoint2 = cxpoint2, cxpoint1

    ind1[cxpoint1:cxpoint2], ind2[cxpoint1:cxpoint2] \
        = ind2[cxpoint1:cxpoint2].copy(), ind1[cxpoint1:cxpoint2].copy()

    return ind1, ind2

def individualCreator():
    """ Create a random individual with safe movements """

    agents = [WanderingAgent( world = nav_map, movement_length = 2, number_of_actions = 8, consecutive_movements = 3) for _ in range(N)]
    actual_position = initial_positions.copy()

    individual = []

    for _ in range(100):
        
        moves = []

        for idx, agent in enumerate(agents):
            action = agent.move(actual_position[idx])
            moves.append(action)
            angle = 2*np.pi * action / 8
            actual_position[idx] = actual_position[idx] + 2 * np.array([np.cos(angle), np.sin(angle)])
        
        individual.append(moves)


    individual_deap = creator.Individual(np.array(individual).reshape(-1))
    
    return individual_deap

# Create a toolbox
toolbox = base.Toolbox()

# Create a creator for the individuals and register 
creator.create("FitnessMax", base.Fitness, weights=(1.0, 1.0))
creator.create("Individual", np.ndarray, fitness=creator.FitnessMax)
toolbox.register("attr_bool", np.random.randint, 0, 8)
toolbox.register("individual", individualCreator)


# Register the population
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# Register the fitness function
toolbox.register("evaluate", fitness_function)

# Register the selection operator
toolbox.register("select", tools.selNSGA2)

# Register the crossover operator
toolbox.register("mate", cxTwoPointCopy)

# Register the mutation operator
toolbox.register("mutate", tools.mutUniformInt, low=0, up=8, indpb=0.1)


if __name__ == '__main__':

    """ Create multi-processing pool """

    # Create a pool
    pool = mp.Pool(processes=8)

    # Register the pool
    toolbox.register("map", pool.map)


    # Register the statistics
    stats = tools.Statistics(lambda ind: ind.fitness.values)

    stats.register("avg", np.mean, axis=0)
    stats.register("std", np.std, axis=0)
    stats.register("min", np.min, axis=0)

    # Create a hall of fame
    hof = tools.ParetoFront(similar=np.array_equal)

    # Create a logbook
    logbook = tools.Logbook()

    """ Run the genetic algorithm """

    # Set the number of generations
    n_generations = 100

    # Set the number of individuals in the population
    n_individuals = 80

    # Set the probability of crossover
    crossover_probability = 0.5

    # Set the probability of mutation
    mutation_probability = 0.2

    for pb in [[0.8, 0.2], [0.7, 0.3], [0.5, 0.2]]:

        # Run the genetic algorithm
        population, logbook = eaMuPlusLambda(population=toolbox.population(n=n_individuals),
                                                toolbox=toolbox,
                                                mu=n_individuals,
                                                lambda_=n_individuals,
                                                cxpb=pb[0],
                                                mutpb=pb[1],
                                                ngen=n_generations,
                                                stats=stats,
                                                halloffame=hof,
                                                verbose=True)            

               

    """ Plot the pareto front """

    # Get the pareto front
    pareto_front = np.array([ind.fitness.values for ind in hof])

    # Plot the pareto front
    plt.figure()
    plt.scatter(pareto_front[:,0], pareto_front[:,1])
    plt.xlabel('W')
    plt.ylabel('I')

    name = 'pareto_front.png'
    plt.savefig(f'SomeOthersScripts/' + name)


    cp = dict(population=population, generation=100, halloffame=hof, logbook=logbook)

    with open(f"SomeOthersScripts/optimization.pkl", "wb") as cp_file:
        pickle.dump(cp, cp_file)
        
    pool.close()







