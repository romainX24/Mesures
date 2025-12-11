#!/usr/bin/env python3
"""Correct blue channel non-linearity by inverting saturation model.

The sensor follows: V_blue = a * (1 - exp(-O*t))
where a = 254.93, O = 0.000025

We invert this to get the linearized value:
V_linear = -a * ln(1 - V/a)

Values can exceed 255 (represents what the reading would be if linear).
"""

import csv
import numpy as np
import matplotlib.pyplot as plt

# Parameters from saturation fit (blue channel)
A_BLUE = 254.9328
O_BLUE = 0.00002499


def correct_blue(v_measured):
    """
    Correct blue channel non-linearity.
    
    Inverts saturation model V = a * (1 - exp(-O*t))
    to get linearized equivalent: V_linear = -a * ln(1 - V/a)
    
    Args:
        v_measured: measured blue value (0-255)
    
    Returns:
        Linearized blue value (can exceed 255)
    """
    v = np.asarray(v_measured, dtype=float)
    v = np.clip(v, 0, A_BLUE - 1e-8)
    ratio = v / A_BLUE
    v_linear = -A_BLUE * np.log(1.0 - ratio)
    return v_linear


def load_csv(path):
    """Load CSV and return exposure and blue channel arrays."""
    xs, b = [], []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                exp = float(row.get('exposure_meta_us', row['exposure_us']))
                b_mean = float(row['b_mean'])
            except Exception:
                continue
            xs.append(exp)
            b.append(b_mean)
    return np.array(xs), np.array(b)


def main():
    csv_path = '/home/urbasense/Mesures/linearity_exposure_20251212_002538.csv'
    xs, b = load_csv(csv_path)
    
    print(f"Blue channel correction (saturation model inversion)")
    print(f"Model: V = {A_BLUE:.2f} * (1 - exp(-{O_BLUE:.8f}*t))")
    print(f"Inverse: V_linear = -{A_BLUE:.2f} * ln(1 - V/{A_BLUE:.2f})")
    print()
    
    # Correct blue channel
    b_corrected = correct_blue(b)
    
    print("Blue channel correction (original → linearized):")
    print("Exp(µs)  | B original | B corrected (linearized)")
    print("-" * 60)
    for i in range(len(xs)):
        print(f"{xs[i]:8.0f} | {b[i]:10.2f} | {b_corrected[i]:10.2f}")
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    order = np.argsort(xs)
    
    # Original (saturating)
    ax1.plot(xs[order], b[order], 'b-o', linewidth=2, markersize=8, label='Original (saturating)')
    ax1.axhline(y=255, color='k', linestyle='--', alpha=0.3, label='Saturation (255)')
    ax1.set_xlabel('Exposition appliquée (µs)', fontsize=11)
    ax1.set_ylabel('Blue pixel value', fontsize=11)
    ax1.set_title('Original Response (Saturating)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Corrected (linear)
    ax2.plot(xs[order], b_corrected[order], 'b-s', linewidth=2, markersize=8, label='Corrected (linearized)')
    ax2.set_xlabel('Exposition appliquée (µs)', fontsize=11)
    ax2.set_ylabel('Blue linearized value', fontsize=11)
    ax2.set_title('Corrected Response (Linear Equivalent)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('/home/urbasense/Mesures/blue_correction.png', dpi=100)
    print()
    print("Plot saved: /home/urbasense/Mesures/blue_correction.png")


if __name__ == '__main__':
    main()
