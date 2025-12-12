#!/usr/bin/env python3
"""Analyze RAW (DNG) images and display R, G, B statistics from center region.

Usage:
  python3 basic_analyze.py <path_to_dng_file>
  
Example:
  python3 basic_analyze.py nu_700nm.dng
"""

import sys
import os

try:
    import numpy as np
except Exception:
    raise SystemExit("NumPy non trouvé.")

try:
    from picamera2 import Picamera2
    from picamera2.request import _MappedBuffer
except Exception:
    raise SystemExit("picamera2 non trouvé.")


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


def analyze_raw(dng_path, crop_size=200):
    """
    Analyze RAW DNG image and extract R, G, B statistics from center.
    
    Args:
        dng_path: Path to DNG file
        crop_size: Size of center square crop (pixels on each side)
    
    Returns:
        Dict with R, G, B statistics (mean, min, max)
    """
    if not os.path.exists(dng_path):
        raise FileNotFoundError(f"File not found: {dng_path}")
    
    # Load raw data from DNG
    raw_data = load_dng_raw(dng_path)
    
    h, w = raw_data.shape
    print(f"Raw image dimensions: {w} x {h}")
    
    # Extract center crop
    cy, cx = h // 2, w // 2
    half = crop_size // 2
    center_crop = raw_data[cy-half:cy+half, cx-half:cx+half]
    
    print(f"Center crop size: {crop_size} x {crop_size}")
    print(f"Center region: rows [{cy-half}:{cy+half}], cols [{cx-half}:{cx+half}]")
    print()
    
    # Extract color channels from Bayer pattern (RGGB)
    # Row 0, Col 0 = R
    # Row 0, Col 1 = G
    # Row 1, Col 0 = G
    # Row 1, Col 1 = B
    
    r_channel = center_crop[0::2, 0::2].flatten()  # Every other row, every other col (R)
    g_channel_1 = center_crop[0::2, 1::2].flatten()  # Row 0, Col 1 (G)
    g_channel_2 = center_crop[1::2, 0::2].flatten()  # Row 1, Col 0 (G)
    b_channel = center_crop[1::2, 1::2].flatten()  # Every other row, every other col (B)
    
    # Combine G channels
    g_channel = np.concatenate([g_channel_1, g_channel_2])
    
    # Calculate statistics
    stats = {
        'R': {
            'mean': float(np.mean(r_channel)),
            'min': int(np.min(r_channel)),
            'max': int(np.max(r_channel)),
            'std': float(np.std(r_channel)),
        },
        'G': {
            'mean': float(np.mean(g_channel)),
            'min': int(np.min(g_channel)),
            'max': int(np.max(g_channel)),
            'std': float(np.std(g_channel)),
        },
        'B': {
            'mean': float(np.mean(b_channel)),
            'min': int(np.min(b_channel)),
            'max': int(np.max(b_channel)),
            'std': float(np.std(b_channel)),
        },
    }
    
    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 basic_analyze.py <path_to_dng_file>")
        print("Example: python3 basic_analyze.py spectral_photos_20251212_012619/nu_700nm.dng")
        sys.exit(1)
    
    dng_path = sys.argv[1]
    
    print("=" * 70)
    print(f"Analyzing: {dng_path}")
    print("=" * 70)
    print()
    
    try:
        stats = analyze_raw(dng_path, crop_size=200)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    
    print("=" * 70)
    print("COLOR CHANNEL STATISTICS (Center 200x200 crop)")
    print("=" * 70)
    print()
    
    for color in ['R', 'G', 'B']:
        s = stats[color]
        print(f"{color} Channel:")
        print(f"  Mean:  {s['mean']:8.2f}")
        print(f"  Min:   {s['min']:8d}")
        print(f"  Max:   {s['max']:8d}")
        print(f"  StdDev:{s['std']:8.2f}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"R: {stats['R']['mean']:.2f} (min={stats['R']['min']}, max={stats['R']['max']})")
    print(f"G: {stats['G']['mean']:.2f} (min={stats['G']['min']}, max={stats['G']['max']})")
    print(f"B: {stats['B']['mean']:.2f} (min={stats['B']['min']}, max={stats['B']['max']})")


if __name__ == '__main__':
    main()
