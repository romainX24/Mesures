#!/usr/bin/env python3
"""Test de linéarité vs temps d'exposition (lumière constante).

Ce script balaye différents temps d'exposition en mode manuel (AE/AGC désactivés),
capture une image traitée en `RGB888` et calcule les moyennes des canaux R, G, B
(sur un crop central pour limiter le vignettage). Il sauvegarde un CSV et un
graphique des courbes R, G, B en fonction du temps d'exposition.

Pré-requis: lumière stable pendant tout le test.
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
    # Flux principal en RGB888 pour obtenir directement R,G,B
    camera_config = picam2.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)}
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


def central_crop_rgb_means(rgb, crop=200):
    # rgb shape: (H, W, 3)
    h, w, _ = rgb.shape
    cy, cx = h // 2, w // 2
    half = crop // 2
    crop_arr = rgb[cy-half:cy+half, cx-half:cx+half, :]
    r = float(np.mean(crop_arr[:, :, 0]))
    g = float(np.mean(crop_arr[:, :, 1]))
    b = float(np.mean(crop_arr[:, :, 2]))
    return r, g, b


def main():
    picam2 = Picamera2()
    # configuration initiale; on ajustera ExposureTime avant chaque capture
    configure_camera(picam2, exposure_us=10000, analogue_gain=1.0)
    picam2.start()
    time.sleep(0.2)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(out_dir, f'linearity_exposure_{timestamp}.csv')

    # Séquence de temps d'exposition (microsecondes). Adaptez selon votre scène.
    exposure_us_list = [200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]
    print('Balayage des temps d\'exposition (us):', exposure_us_list)
    print('Assurez une lumière constante pendant tout le test.')

    records = []

    for exp_us in exposure_us_list:
        # Fixer le temps d'expo (AE off)
        picam2.set_controls({"ExposureTime": int(exp_us), "AeEnable": 0})
        time.sleep(0.15)  # laisser le temps de prise en compte

        req = picam2.capture_request()
        rgb = req.make_array('main')  # RGB888
        # sécurité: vérifier dimensions
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            req.release()
            print('Format inattendu pour main stream, abandon.')
            break
        r_mean, g_mean, b_mean = central_crop_rgb_means(rgb, crop=200)
        req.release()

        # Lire quelques métadonnées utiles
        meta = picam2.capture_metadata()
        analogue_gain = float(meta.get('AnalogueGain', np.nan))
        exposure_readback = float(meta.get('ExposureTime', np.nan))

        print(f"✓ Exp={exp_us} us (meta {exposure_readback} us) | R={r_mean:.2f} G={g_mean:.2f} B={b_mean:.2f} | Gain={analogue_gain}")
        records.append({
            'exposure_us': exp_us,
            'exposure_meta_us': exposure_readback,
            'analogue_gain': analogue_gain,
            'r_mean': r_mean,
            'g_mean': g_mean,
            'b_mean': b_mean,
        })

    picam2.stop()

    # Sauvegarde CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['exposure_us', 'exposure_meta_us', 'analogue_gain', 'r_mean', 'g_mean', 'b_mean'])
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)
    print(f'CSV sauvegardé: {csv_path}')

    # Graphique R,G,B vs exposure_us
    if plt is not None and records:
        xs = np.array([rec['exposure_us'] for rec in records], dtype=float)
        r = np.array([rec['r_mean'] for rec in records], dtype=float)
        g = np.array([rec['g_mean'] for rec in records], dtype=float)
        b = np.array([rec['b_mean'] for rec in records], dtype=float)

        plt.figure(figsize=(7,4))
        plt.plot(xs, r, 'r-o', label='R')
        plt.plot(xs, g, 'g-o', label='G')
        plt.plot(xs, b, 'b-o', label='B')
        plt.xlabel('Temps d\'exposition (µs)')
        plt.ylabel('Moyenne canal (RGB888)')
        plt.title('Moyennes R,G,B vs temps d\'exposition (lumière constante)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        png_path = os.path.join(out_dir, f'linearity_exposure_plot_{timestamp}.png')
        plt.savefig(png_path)
        print(f'Graphique sauvegardé: {png_path}')
    else:
        print('matplotlib non disponible ou aucun enregistrement — pas de graphique généré.')

    print('Terminé.')


if __name__ == '__main__':
    main()
