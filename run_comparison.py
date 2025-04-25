import subprocess

for i in range(1, 41, 1):
    with open('benchs/data/experiment_baseline.txt', 'a') as f:
        f.write(f'----- {i*60}\n')
    with open('benchs/data/experiment.txt', 'a') as f:
        f.write(f'----- {i*60}\n')
    for k in range(10):
        # set amount of tokens in each net, amount of transitions, amount of nets
        nets_process = subprocess.Popen(['python', 'nets_generator.py', str(1), str(i * 60), str(i * 30)])
        nets_process.wait()

        # set length
        main_process = subprocess.Popen(['python', 'workflow_proposed_algorithm.py', str(int(10))], shell=False)
        try:
            main_process.wait()
        except subprocess.TimeoutExpired:
            print("Main process did not terminate gracefully, forcing exit")
            main_process.kill()
