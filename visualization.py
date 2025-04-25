import numpy as np
import matplotlib.pyplot as plt
from matplotlib import ticker


def parse_file(filename):
    data = {}
    current_param = None
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('-----'):
                current_param = int(line.split()[-1])
                data[current_param] = []
            else:
                if current_param is not None and line:
                    data[current_param].append(float(line))
    return data


def prepare_stats(data_dict):
    params = list(data_dict.keys())
    means, p25, p75 = [], [], []
    for param in params:
        values = data_dict[param]
        means.append(np.mean(values))
        p25.append(np.percentile(values, 25))
        p75.append(np.percentile(values, 75))
    return params, means, p25, p75


data_alg1 = parse_file("benchs/data/proposed_i_times_10_10000.txt")  # Replace with your first file path
data_alg2 = parse_file("benchs/data/classic_i_times_10_10000.txt")  # Replace with your second file path
params1, means1, p25_1, p75_1 = prepare_stats(data_alg1)
params2, means2, p25_2, p75_2 = prepare_stats(data_alg2)

plt.figure(figsize=(12, 6))

plt.plot(params1, means1, 'b-o', label='Среднее кол-во активаций предложенного алгоритма', linewidth=2)
plt.fill_between(params1, p25_1, p75_1, color='blue', alpha=0.2,
                 label='Межквартильный размах кол-ва активаций предложенного алгоритма')

plt.plot(params2, means2, 'r-s', label='Среднее кол-во активаций классического алгоритма', linewidth=2)
plt.fill_between(params2, p25_2, p75_2, color='red', alpha=0.2,
                 label='Межквартильный размах кол-ва активаций классического алгоритма')

plt.xlabel('Количество переходов в сети', fontsize=15)
plt.yscale("log")
plt.ylabel('Количество активаций переходов, $log_{10}$', fontsize=15)

ax = plt.gca()
y_ticks = np.logspace(np.log10(min(min(p25_1), min(p25_2))), np.log10(max(max(p75_1), max(p75_2))), num=10)
x_ticks = range(60, max(params1) + 1, 120)
ax.set_yticks(y_ticks)
ax.set_xticks(x_ticks)

plt.minorticks_off()
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: round(np.log10(x), 2)))

plt.legend(loc='best', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()
# plt.savefig("benchs/graphs/1000-len.pdf")
