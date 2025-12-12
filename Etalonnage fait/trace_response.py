#!/usr/bin/env python3
"""Trace la réponse spectrale R, G, B en fonction de la longueur d'onde.

Lit tous les fichiers nu_XXXnm.dng dans le dossier courant,
extrait les moyennes R, G, B sur un carré de 100x100 pixels au centre,
et trace les courbes de réponse spectrale.

Usage:
  cd "Etalonnage fait"
  python3 trace_response.py
"""

import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt


def load_dng_raw(dng_path):
    """Load RAW data from DNG file using basic TIFF parsing."""
    import struct
    
    with open(dng_path, 'rb') as f:
        # Read TIFF header
        byte_order = f.read(2)
        if byte_order == b'II':  # Little endian
            endian = '<'
        elif byte_order == b'MM':  # Big endian
            endian = '>'
        else:
            raise ValueError("Not a valid TIFF/DNG file")
        
        magic = struct.unpack(f'{endian}H', f.read(2))[0]
        if magic != 42:
            raise ValueError("Not a valid TIFF file")
        
        # Read IFD offset
        ifd_offset = struct.unpack(f'{endian}I', f.read(4))[0]
        
        # Go to IFD
        f.seek(ifd_offset)
        
        # Read number of directory entries
        num_entries = struct.unpack(f'{endian}H', f.read(2))[0]
        
        width = None
        height = None
        strip_offset = None
        strip_bytes = None
        bits_per_sample = None
        
        # Read IFD entries
        for _ in range(num_entries):
            tag = struct.unpack(f'{endian}H', f.read(2))[0]
            field_type = struct.unpack(f'{endian}H', f.read(2))[0]
            count = struct.unpack(f'{endian}I', f.read(4))[0]
            value_offset = f.read(4)
            
            if tag == 256:  # ImageWidth
                width = struct.unpack(f'{endian}I', value_offset)[0]
            elif tag == 257:  # ImageLength
                height = struct.unpack(f'{endian}I', value_offset)[0]
            elif tag == 258:  # BitsPerSample
                bits_per_sample = struct.unpack(f'{endian}H', value_offset[:2])[0]
            elif tag == 273:  # StripOffsets
                strip_offset = struct.unpack(f'{endian}I', value_offset)[0]
            elif tag == 279:  # StripByteCounts
                strip_bytes = struct.unpack(f'{endian}I', value_offset)[0]
        
        if None in (width, height, strip_offset, strip_bytes):
            raise ValueError("Could not extract image dimensions from DNG")
        
        # Read raw data
        f.seek(strip_offset)
        raw_bytes = f.read(strip_bytes)
        
        # For 10-bit packed data (5 bytes = 4 pixels of 10 bits each)
        if bits_per_sample == 10:
            # Unpack 10-bit data
            num_pixels = (len(raw_bytes) * 8) // 10
            raw_data = np.zeros(num_pixels, dtype=np.uint16)
            
            byte_idx = 0
            for i in range(0, num_pixels, 4):
                if byte_idx + 4 >= len(raw_bytes):
                    break
                # 5 bytes contain 4 pixels of 10 bits
                b0, b1, b2, b3, b4 = raw_bytes[byte_idx:byte_idx+5]
                raw_data[i+0] = (b0 << 2) | (b1 >> 6)
                raw_data[i+1] = ((b1 & 0x3F) << 4) | (b2 >> 4)
                raw_data[i+2] = ((b2 & 0x0F) << 6) | (b3 >> 2)
                raw_data[i+3] = ((b3 & 0x03) << 8) | b4
                byte_idx += 5
            
            # Trim to actual size
            raw_data = raw_data[:width*height]
        elif bits_per_sample == 16:
            raw_data = np.frombuffer(raw_bytes, dtype=f'{endian}u2')
        else:
            raw_data = np.frombuffer(raw_bytes, dtype=np.uint16)
        
        # Reshape
        raw_data = raw_data.reshape((height, width))
        
        return raw_data


def extract_rgb_from_center(raw_data, crop_size=100):
    """
    Extract R, G, B means from center crop of Bayer pattern image.
    
    Args:
        raw_data: 2D numpy array with Bayer pattern
        crop_size: Size of center square crop
    
    Returns:
        (r_mean, g_mean, b_mean)
    """
    h, w = raw_data.shape
    cy, cx = h // 2, w // 2
    half = crop_size // 2
    center_crop = raw_data[cy-half:cy+half, cx-half:cx+half]
    
    # Extract Bayer channels (RGGB pattern)
    r_channel = center_crop[0::2, 0::2].flatten()
    g_channel_1 = center_crop[0::2, 1::2].flatten()
    g_channel_2 = center_crop[1::2, 0::2].flatten()
    b_channel = center_crop[1::2, 1::2].flatten()
    
    # Combine G channels and compute means
    g_channel = np.concatenate([g_channel_1, g_channel_2])
    
    r_mean = float(np.mean(r_channel))
    g_mean = float(np.mean(g_channel))
    b_mean = float(np.mean(b_channel))
    
    return r_mean, g_mean, b_mean


def main():
    # Find all nu_XXXnm.dng files in current directory
    dng_files = sorted(glob.glob('nu_*nm.dng'))
    
    if not dng_files:
        print("✗ Aucun fichier nu_XXXnm.dng trouvé dans le dossier courant.")
        print("  Assurez-vous d'exécuter ce script depuis le dossier 'Etalonnage fait'")
        return
    
    print(f"Trouvé {len(dng_files)} fichiers DNG")
    print("Extraction des données R, G, B (centre 100x100 pixels)...\n")
    
    # Extract wavelength and RGB values
    wavelengths = []
    r_values = []
    g_values = []
    b_values = []
    
    for dng_file in dng_files:
        # Extract wavelength from filename
        match = re.search(r'nu_(\d+)nm\.dng', dng_file)
        if not match:
            continue
        
        wavelength = int(match.group(1))
        
        try:
            # Load raw data
            raw_data = load_dng_raw(dng_file)
            
            # Extract RGB means
            r_mean, g_mean, b_mean = extract_rgb_from_center(raw_data, crop_size=100)
            
            wavelengths.append(wavelength)
            r_values.append(r_mean)
            g_values.append(g_mean)
            b_values.append(b_mean)
            
            print(f"✓ {wavelength:4d} nm: R={r_mean:7.2f}, G={g_mean:7.2f}, B={b_mean:7.2f}")
            
        except Exception as e:
            print(f"✗ {dng_file}: {e}")
    
    if not wavelengths:
        print("\n✗ Aucune donnée extraite.")
        return
    
    # Convert to numpy arrays
    wavelengths = np.array(wavelengths)
    r_values = np.array(r_values)
    g_values = np.array(g_values)
    b_values = np.array(b_values)
    
    # Sort by wavelength
    order = np.argsort(wavelengths)
    wavelengths = wavelengths[order]
    r_values = r_values[order]
    g_values = g_values[order]
    b_values = b_values[order]
    
    print(f"\n✓ {len(wavelengths)} points extraits avec succès")
    print("\nTraçage des courbes de réponse spectrale...")
    
    # Plot spectral response
    plt.figure(figsize=(10, 6))
    plt.plot(wavelengths, r_values, 'r-o', label='R (Rouge)', linewidth=2, markersize=6)
    plt.plot(wavelengths, g_values, 'g-s', label='G (Vert)', linewidth=2, markersize=6)
    plt.plot(wavelengths, b_values, 'b-^', label='B (Bleu)', linewidth=2, markersize=6)
    
    plt.xlabel('Longueur d\'onde (nm)', fontsize=12)
    plt.ylabel('Intensité (valeur RAW moyenne)', fontsize=12)
    plt.title('Réponse spectrale des canaux R, G, B\n(moyenne sur 100×100 pixels au centre)', fontsize=13, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save plot
    output_path = 'spectral_response.png'
    plt.savefig(output_path, dpi=150)
    print(f"✓ Graphique sauvegardé: {output_path}")
    
    # Save CSV
    csv_path = 'spectral_response.csv'
    with open(csv_path, 'w') as f:
        f.write('wavelength_nm,R_mean,G_mean,B_mean\n')
        for i in range(len(wavelengths)):
            f.write(f'{wavelengths[i]},{r_values[i]:.4f},{g_values[i]:.4f},{b_values[i]:.4f}\n')
    print(f"✓ Données sauvegardées: {csv_path}")


if __name__ == '__main__':
    main()
