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
        # Désactiver flicker (si supporté) pour éviter quantification 50/60 Hz
        "AeFlickerMode": 0,
        "ExposureTime": int(exposure_us),
        # Étendre la durée de trame par défaut pour permettre des expositions longues
        "FrameDurationLimits": (250000, 250000),  # 250 ms
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


def wait_until_exposure_applied(picam2, target_us, max_wait_s=1.0, tol_frac=0.05):
    """Capture des frames jusqu'à ce que les métadonnées reflètent ~target_us.
    Retourne (applied_us, last_meta)."""
    deadline = time.time() + max_wait_s
    applied_us = float('nan')
    last_meta = {}
    while time.time() < deadline:
        req = picam2.capture_request()
        meta = req.get_metadata()
        req.release()
        applied_us = float(meta.get('ExposureTime', float('nan')))
        if np.isfinite(applied_us) and target_us > 0:
            if abs(applied_us - target_us) / target_us <= tol_frac:
                return applied_us, meta
        last_meta = meta
    return applied_us, last_meta


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
    exposure_us_list = [100,300, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000,150000, 200000]
    print('Balayage des temps d\'exposition (us):', exposure_us_list)
    print('Assurez une lumière constante pendant tout le test.')

    records = []

    for exp_us in exposure_us_list:
        # Fixer le temps d'expo et la durée de trame pour permettre des expositions longues
        # FrameDurationLimits est un tuple (min_us, max_us)
        picam2.set_controls({
            "AeEnable": 0,
            "AnalogueGain": 1.0,
            "FrameDurationLimits": (int(exp_us), int(exp_us)),
            "ExposureTime": int(exp_us),
        })
        time.sleep(0.05)  # petite latence

        # Attendre que la valeur soit appliquée (tolérance 5%)
        applied_us, meta_applied = wait_until_exposure_applied(picam2, exp_us, max_wait_s=1.0, tol_frac=0.05)
        if not np.isfinite(applied_us):
            # réessayer en imposant de nouveau FrameDurationLimits
            picam2.set_controls({"FrameDurationLimits": (int(exp_us), int(exp_us))})
            applied_us, meta_applied = wait_until_exposure_applied(picam2, exp_us, max_wait_s=1.0, tol_frac=0.05)

        # Capture de mesure
        req = picam2.capture_request()
        rgb = req.make_array('main')  # RGB888
        # sécurité: vérifier dimensions
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            meta = req.get_metadata()
            req.release()
            print('Format inattendu pour main stream, abandon.')
            break
        r_mean, g_mean, b_mean = central_crop_rgb_means(rgb, crop=200)

        # Lire les métadonnées associées à CETTE capture
        meta = req.get_metadata()
        req.release()

        analogue_gain = float(meta.get('AnalogueGain', np.nan))
        exposure_readback = float(meta.get('ExposureTime', np.nan))
        frame_limits = meta.get('FrameDurationLimits', None)

        status = "OK" if np.isfinite(applied_us) and abs(applied_us - exp_us) / max(exp_us, 1) <= 0.05 else "CLAMPED"
        print(f"✓ Exp={exp_us} us (meta {exposure_readback} us, limits={frame_limits}, status={status}) | R={r_mean:.2f} G={g_mean:.2f} B={b_mean:.2f} | Gain={analogue_gain}")
        records.append({
            'exposure_us': exp_us,
            'exposure_meta_us': exposure_readback,
            'analogue_gain': analogue_gain,
            'r_mean': r_mean,
            'g_mean': g_mean,
            'b_mean': b_mean,
            'frame_limits': frame_limits,
            'status': status,
        })

    picam2.stop()

    # Sauvegarde CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['exposure_us', 'exposure_meta_us', 'analogue_gain', 'r_mean', 'g_mean', 'b_mean', 'frame_limits', 'status']
        )
        writer.writeheader()
        for rec in records:
            # Normaliser frame_limits pour CSV
            fl = rec.get('frame_limits', None)
            rec['frame_limits'] = '' if fl is None else str(fl)
            writer.writerow(rec)
    print(f'CSV sauvegardé: {csv_path}')

    # Graphique R,G,B vs exposure_meta_us (exposition réellement appliquée)
    if plt is not None and records:
        xs = np.array([rec['exposure_meta_us'] for rec in records], dtype=float)
        r = np.array([rec['r_mean'] for rec in records], dtype=float)
        g = np.array([rec['g_mean'] for rec in records], dtype=float)
        b = np.array([rec['b_mean'] for rec in records], dtype=float)

        # Trier par X pour des courbes propres
        order = np.argsort(xs)
        xs, r, g, b = xs[order], r[order], g[order], b[order]

        plt.figure(figsize=(7,4))
        plt.plot(xs, r, 'r-o', label='R')
        plt.plot(xs, g, 'g-o', label='G')
        plt.plot(xs, b, 'b-o', label='B')
        plt.xlabel('Temps d\'exposition (µs)')
        plt.ylabel('Moyenne canal (RGB888)')
        plt.title('Moyennes R,G,B vs exposition (meta µs, lumière constante)')
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
