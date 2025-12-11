#!/usr/bin/env python3
"""Test de linéarité caméra vs éclairement (interactif).

Usage:
  - Lancez le script près de la scène.
  - Vérifiez que vous avez un luxmètre indépendant pour fournir la valeur de référence.
  - Pour chaque niveau d'éclairement: entrez la valeur lux mesurée, appuyez sur Entrée -> le script capture une image RAW et enregistre la moyenne de pixels.
  - À la fin (tapez 'q'), le script calcule une régression linéaire et sauvegarde les résultats en CSV et PNG.

Le script force le mode manuel (exposure/gain) pour éviter l'AGC.
"""

import time
import csv
import os
from datetime import datetime

try:
    from picamera2 import Picamera2
except Exception as e:
    raise SystemExit("picamera2 non trouvé. Ce script doit s'exécuter sur Raspberry Pi avec picamera2.")

import numpy as np
import math
try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def configure_camera(picam2, exposure_us=10000, analogue_gain=1.0):
    camera_config = picam2.create_preview_configuration(
        main={"format": 'XRGB8888', "size": (640, 480)},
        raw={"format": "SBGGR10", "size": (3280, 2464)}
    )
    camera_config["controls"] = {
        "AwbEnable": 0,
        "AnalogueGain": analogue_gain,
        "AnalogueGainMode": 0,
        "ExposureTimeMode": 0,
        "AeEnable": 0,
        "ExposureTime": int(exposure_us),
        "ColourTemperature": 5500,
    }
    picam2.configure(camera_config)


def central_crop_mean(arr, crop=200):
    h, w = arr.shape
    cy, cx = h // 2, w // 2
    half = crop // 2
    crop_arr = arr[cy-half:cy+half, cx-half:cx+half]
    # mask possible zeros
    flat = crop_arr.flatten()
    flat = flat[flat > 0]
    if flat.size == 0:
        return float(np.mean(crop_arr))
    return float(np.mean(flat))


def main():
    picam2 = Picamera2()
    configure_camera(picam2)
    picam2.start()
    time.sleep(0.2)

    samples = []
    out_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(out_dir, f'linearity_results_{timestamp}.csv')

    print("Test de linéarité caméra vs éclairement")
    print("Pour chaque niveau d'éclairement: entrez la valeur lux mesurée (par ex. 100) puis Entrée.")
    print("Tapez 'q' pour quitter et lancer l'analyse.")

    while True:
        val = input('Lux (q pour quitter) > ').strip()
        if val.lower() in ('q', 'quit'):
            break
        try:
            lux = float(val)
        except ValueError:
            print('Entrée non reconnue, réessayez.')
            continue

        # capture
        print('Capture en cours...')
        req = picam2.capture_request()
        raw = req.make_array('raw')
        mean_raw = central_crop_mean(raw, crop=400)
        minv = float(raw.min())
        maxv = float(raw.max())
        req.release()

        print(f'✓ Capturé: mean_raw={mean_raw:.3f} min={minv} max={maxv}')
        samples.append({'lux': lux, 'mean_raw': mean_raw, 'min': minv, 'max': maxv, 'timestamp': datetime.now().isoformat()})

    picam2.stop()

    if not samples:
        print('Aucun échantillon acquis. Fin.')
        return

    # Write CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'lux', 'mean_raw', 'min', 'max'])
        writer.writeheader()
        for s in samples:
            writer.writerow(s)

    print(f'CSV sauvegardé: {csv_path}')

    # Analysis: fit mean_raw = a * lux + b
    lux_arr = np.array([s['lux'] for s in samples], dtype=float)
    y = np.array([s['mean_raw'] for s in samples], dtype=float)

    # Simple linear fit
    coef = np.polyfit(lux_arr, y, 1)
    a, b = coef[0], coef[1]
    y_pred = a * lux_arr + b
    # R^2
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else float('nan')

    print('\nRésultats de la régression linéaire:')
    print(f'  mean_raw = a * lux + b')
    print(f'  a = {a:.6f}, b = {b:.6f}, R² = {r2:.6f}')

    # Plot
    if plt is not None:
        plt.figure(figsize=(6,4))
        plt.scatter(lux_arr, y, label='mesures')
        xs = np.linspace(lux_arr.min(), lux_arr.max(), 200)
        plt.plot(xs, a*xs + b, 'r-', label=f'fit: y={a:.3e}x+{b:.1f}\nR²={r2:.4f}')
        plt.xlabel('Lux (référence)')
        plt.ylabel('Mean RAW pixel value')
        plt.legend()
        plt.tight_layout()
        png_path = os.path.join(out_dir, f'linearity_plot_{timestamp}.png')
        plt.savefig(png_path)
        print(f'Graphique sauvegardé: {png_path}')
    else:
        print('matplotlib non disponible — pas de graphique généré.')

    print('Terminé.')


if __name__ == '__main__':
    main()
