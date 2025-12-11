#!/usr/bin/env python3
"""Fit curves to B, G, R channels and find best model."""

import csv
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

def load_csv(path):
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

# Models
def linear(x, a, b):
    return a * x + b

def saturation_exp(x, a, O):
    """a * (1 - exp(-O * x))"""
    return a * (1.0 - np.exp(-O * x))

def power_law(x, a, p):
    """a * x^p"""
    return a * np.power(x, p)

def logarithmic(x, a, b):
    """a * log(x) + b"""
    return a * np.log(x) + b

def fit_model(x, y, model, p0, label):
    try:
        popt, pcov = curve_fit(model, x, y, p0=p0, maxfev=10000)
        y_pred = model(x, *popt)
        residuals = y - y_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else float('nan')
        rmse = np.sqrt(np.mean(residuals**2))
        return {
            'label': label,
            'model_func': model,
            'popt': popt,
            'r2': r2,
            'rmse': rmse,
            'y_pred': y_pred,
        }
    except Exception as e:
        print(f"  ✗ {label}: {e}")
        return None

def main():
    csv_path = '/home/urbasense/Mesures/linearity_exposure_20251212_002538.csv'
    xs, r, g, b = load_csv(csv_path)
    
    print("Fitting models to Blue channel:")
    print(f"Data points: {len(xs)}")
    print(f"X range: {xs.min():.1f} — {xs.max():.1f} µs")
    print(f"Y range: {b.min():.2f} — {b.max():.2f}")
    print()
    
    fits = []
    
    # Linear: a*x + b
    print("1. Linear fit: y = a*x + b")
    fit = fit_model(xs, b, linear, [1.0, 0.0], "Linear")
    if fit:
        print(f"   y = {fit['popt'][0]:.6f}*x + {fit['popt'][1]:.4f}")
        print(f"   R² = {fit['r2']:.6f}, RMSE = {fit['rmse']:.4f}")
        fits.append(fit)
    print()
    
    # Saturation (exponential): a * (1 - exp(-O*x))
    print("2. Saturation fit: y = a * (1 - exp(-O*x))")
    fit = fit_model(xs, b, saturation_exp, [255.0, 1e-5], "Saturation")
    if fit:
        a, O = fit['popt']
        print(f"   y = {a:.4f} * (1 - exp(-{O:.8f}*x))")
        print(f"   a (asymptote) = {a:.4f}, O = {O:.8f}")
        print(f"   R² = {fit['r2']:.6f}, RMSE = {fit['rmse']:.4f}")
        fits.append(fit)
    print()
    
    # Power law: a * x^p
    print("3. Power law fit: y = a * x^p")
    fit = fit_model(xs, b, power_law, [0.01, 0.5], "Power law")
    if fit:
        a, p = fit['popt']
        print(f"   y = {a:.6f} * x^{p:.6f}")
        print(f"   R² = {fit['r2']:.6f}, RMSE = {fit['rmse']:.4f}")
        fits.append(fit)
    print()
    
    # Logarithmic: a * log(x) + b
    print("4. Logarithmic fit: y = a * log(x) + b")
    fit = fit_model(xs, b, logarithmic, [10.0, 0.0], "Logarithmic")
    if fit:
        a, b_coef = fit['popt']
        print(f"   y = {a:.6f} * log(x) + {b_coef:.4f}")
        print(f"   R² = {fit['r2']:.6f}, RMSE = {fit['rmse']:.4f}")
        fits.append(fit)
    print()
    
    # Rank by R²
    print("=" * 60)
    print("RANKING BY R²:")
    fits_sorted = sorted(fits, key=lambda x: x['r2'], reverse=True)
    for i, fit in enumerate(fits_sorted, 1):
        print(f"{i}. {fit['label']}: R² = {fit['r2']:.6f}, RMSE = {fit['rmse']:.4f}")
    
    best = fits_sorted[0]
    print()
    print(f"✓ BEST FIT: {best['label']}")
    print()
    
    # Plot with smooth best fit
    plt.figure(figsize=(10, 6))
    
    # Scatter plot
    order = np.argsort(xs)
    plt.scatter(xs[order], b[order], s=80, alpha=0.8, label='Data', color='blue', zorder=5)
    
    # Smooth best fit line (many interpolated points)
    xs_smooth = np.linspace(xs.min(), xs.max(), 500)
    y_smooth = best['model_func'](xs_smooth, *best['popt'])
    plt.plot(xs_smooth, y_smooth, 'r-', linewidth=3, label=f"Best: {best['label']} (R²={best['r2']:.4f})", zorder=3)
    
    plt.xlabel("Exposition appliquée (µs)", fontsize=12)
    plt.ylabel("Blue channel mean (RGB888)", fontsize=12)
    plt.title("Blue channel saturation model: 255(1 - exp(-O·t))", fontsize=13, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('/home/urbasense/Mesures/blue_curve_fit.png', dpi=100)
    print("Plot saved: /home/urbasense/Mesures/blue_curve_fit.png")

if __name__ == '__main__':
    main()
