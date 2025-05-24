import subprocess

from config import BASELINE_BENCH_FILE_PATH, PROPOSED_BENCH_FILE_PATH

for i in range(1, 41, 1):
    with open(BASELINE_BENCH_FILE_PATH, 'a') as f:
        f.write(f'----- {i*60}\n')
    with open(PROPOSED_BENCH_FILE_PATH, 'a') as f:
        f.write(f'----- {i*60}\n')
    for k in range(10):
        nets_process = subprocess.Popen(['python', 'benchmark_utilities/nets_generator.py',
                                         str(1), str(i * 60), str(0.8), str(i * 6)])
        nets_process.wait()

        main_process = subprocess.Popen(['python', 'workflow_proposed_algorithm.py', str(int(1000))], shell=False)
        try:
            main_process.wait()
        except subprocess.TimeoutExpired:
            print("Main process did not terminate gracefully, forcing exit")
            main_process.kill()
