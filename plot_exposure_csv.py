
#!/usr/bin/env python3
import sys
import csv
import os

import numpy as np
import matplotlib.pyplot as plt


def load_csv(path):
    xs, r, g, b = [], [], [], []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # utiliser l'exposition réellement appliquée
                exp = float(row.get('exposure_meta_us', row['exposure_us']))
                r_mean = float(row['r_mean'])
                g_mean = float(row['g_mean'])
                b_mean = float(row['b_mean'])
            except Exception:
                continue
            xs.append(exp)
            r.append(r_mean)
            g.append(g_mean)
            b.append(b_mean)
    return np.array(xs), np.array(r), np.array(g), np.array(b)


def plot_rgb_vs_exposure(csv_path):
    xs, r, g, b = load_csv(csv_path)
    if xs.size == 0:
        print('Aucune donnée lisible dans le CSV.')
        return
    # Trier par X pour des courbes propres
    order = np.argsort(xs)
    xs, r, g, b = xs[order], r[order], g[order], b[order]
    plt.figure(figsize=(7,4))
    plt.plot(xs, r, 'r-o', label='R')
    plt.plot(xs, g, 'g-o', label='G')
    plt.plot(xs, b, 'b-o', label='B')
    plt.xlabel("Exposition appliquée (meta µs)")
    plt.ylabel('Moyenne canal (RGB888)')
    plt.title("R, G, B vs exposition (meta µs)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    out_png = os.path.splitext(csv_path)[0] + '_plot.png'
    plt.savefig(out_png)
    print('Graphique sauvegardé:', out_png)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 plot_exposure_csv.py <path_to_csv>')
        sys.exit(1)
    plot_rgb_vs_exposure(sys.argv[1])
