import numpy as np
import matplotlib.pyplot as plt


def parse_file(filename):
    data_init = {}
    data_exec = {}
    current_param = None
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('-----'):
                current_param = int(line.split()[-1])
                data_init[current_param] = []
                data_exec[current_param] = []
            elif line:
                init, exec_time = map(float, line.split(', '))
                data_init[current_param].append(init)
                data_exec[current_param].append(exec_time)
    return data_init, data_exec


def prepare_stats(data_dict):
    params = sorted(data_dict.keys())
    means, p25, p75 = [], [], []
    for param in params:
        values = data_dict[param]
        means.append(np.mean(values))
        p25.append(np.percentile(values, 25))
        p75.append(np.percentile(values, 75))
    return params, means, p25, p75


init_data, exec_data = parse_file("benchs/data/proposed_init_analyze_10_per_agent.txt")
params, init_means, init_p25, init_p75 = prepare_stats(init_data)
_, exec_means, exec_p25, exec_p75 = prepare_stats(exec_data)

init_errors = np.array([np.array(init_means) - np.array(init_p25),
                        np.array(init_p75) - np.array(init_means)])
init_errors = init_errors.clip(min=0)
exec_errors = np.array([np.array(exec_means) - np.array(exec_p25),
                        np.array(exec_p75) - np.array(exec_means)])
exec_errors = exec_errors.clip(min=0)

fig, ax1 = plt.subplots(1, 1, figsize=(15, 6))
ax1.bar(params, init_means)
ax1.set_title('Время инициализации')
ax1.set_xlabel('Количество переходов')
ax1.set_ylabel('Секунды')
ax1.grid(True, linestyle='--', alpha=0.7)
ax1.bar(params, exec_means)

plt.tight_layout()
plt.show()
plt.savefig("benchs/graphs/proposed_precheck_4_1000.pdf")
