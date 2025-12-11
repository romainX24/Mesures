#!/usr/bin/env python3
"""Correct sensor non-linearity by inverting saturation model.

The sensor follows: V = a * (1 - exp(-O*t))
We use the initial slope (a*O) as the linear reference.

Given a measured value V, we:
1. Find the equivalent exposure time t that produced this V
2. Apply the reference slope to get the linear equivalent

Formula: V_linear = a*O * (-ln(1 - V/a) / O) = -a * ln(1 - V/a)
"""

import csv
import numpy as np
import matplotlib.pyplot as plt

# Parameters from saturation fit (blue channel)
A_BLUE = 254.9328
O_BLUE = 0.00002499

# Estimate for R and G (you can refine with separate fits)
A_RED = 255.0      # Asymptote
A_GREEN = 255.0    # Asymptote
O_RED = 5e-5       # Slower saturation (red is more linear)
O_GREEN = 3e-5     # Between blue and red


def correct_nonlinearity(v_measured, a, O):
    """
    Correct non-linear saturation response to linear equivalent.
    
    Given a measured value (0-255) from saturation response:
    V = a * (1 - exp(-O*t))
    
    Return the linear equivalent:
    V_linear = -a * ln(1 - V/a) = slope * t_equiv
    
    where slope = a*O is the reference (initial linear slope).
    """
    # Convert to numpy array for uniform handling
    v = np.asarray(v_measured)
    v = np.clip(v, 0, a - 1e-8)
    
    # Invert saturation to get equivalent linear response
    # V_linear = -a * ln(1 - V/a)
    ratio = v / a
    v_linear = -a * np.log(1.0 - ratio)
    
    return v_linear


def load_csv(path):
    """Load CSV and return exposure, R, G, B arrays."""
    xs, r, g, b = [], [], [], []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
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


def main():
    csv_path = '/home/urbasense/Mesures/linearity_exposure_20251212_002538.csv'
    xs, r, g, b = load_csv(csv_path)
    
    print("Correcting non-linearity using saturation model inversion")
    print(f"Blue:  V = {A_BLUE:.2f} * (1 - exp(-{O_BLUE:.8f}*t))")
    print(f"Green: V = {A_GREEN:.2f} * (1 - exp(-{O_GREEN:.8f}*t))")
    print(f"Red:   V = {A_RED:.2f} * (1 - exp(-{O_RED:.8f}*t))")
    print()
    
    # Correct each channel
    r_corrected = correct_nonlinearity(r, A_RED, O_RED)
    g_corrected = correct_nonlinearity(g, A_GREEN, O_GREEN)
    b_corrected = correct_nonlinearity(b, A_BLUE, O_BLUE)
    
    # Normalize corrected values to [0, 255] range for display
    def normalize_to_255(vals):
        """Normalize to [0, 255] using the max value as reference."""
        max_val = np.nanmax(vals)
        if max_val <= 0:
            return np.zeros_like(vals)
        return 255.0 * vals / max_val
    
    r_corrected_norm = normalize_to_255(r_corrected)
    g_corrected_norm = normalize_to_255(g_corrected)
    b_corrected_norm = normalize_to_255(b_corrected)
    
    print("Comparison (original → corrected & normalized):")
    print("Exp(µs)  | R orig → corr | G orig → corr | B orig → corr")
    print("-" * 65)
    for i in range(len(xs)):
        print(f"{xs[i]:8.0f} | {r[i]:6.2f}→{r_corrected_norm[i]:6.2f} | {g[i]:6.2f}→{g_corrected_norm[i]:6.2f} | {b[i]:6.2f}→{b_corrected_norm[i]:6.2f}")
    
    # Plot
    plt.figure(figsize=(12, 8))
    
    order = np.argsort(xs)
    
    # Original curves
    plt.subplot(2, 1, 1)
    plt.plot(xs[order], r[order], 'r-o', label='R original', alpha=0.7)
    plt.plot(xs[order], g[order], 'g-o', label='G original', alpha=0.7)
    plt.plot(xs[order], b[order], 'b-o', label='B original', alpha=0.7)
    plt.ylabel('Pixel value (original)')
    plt.title('Original (saturating) response')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Corrected (normalized) curves
    plt.subplot(2, 1, 2)
    plt.plot(xs[order], r_corrected_norm[order], 'r-s', label='R corrected', alpha=0.7)
    plt.plot(xs[order], g_corrected_norm[order], 'g-s', label='G corrected', alpha=0.7)
    plt.plot(xs[order], b_corrected_norm[order], 'b-s', label='B corrected', alpha=0.7)
    plt.xlabel('Exposition appliquée (µs)')
    plt.ylabel('Pixel value (linearized & normalized)')
    plt.title('Linearized response (correction applied)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('/home/urbasense/Mesures/linearization_correction.png', dpi=100)
    print()
    print("Plot saved: /home/urbasense/Mesures/linearization_correction.png")


if __name__ == '__main__':
    main()
