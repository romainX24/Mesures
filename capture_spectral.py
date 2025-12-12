#!/usr/bin/env python3
"""Interactive script to capture spectral photos in RAW (DNG) format with wavelength labeling.

Usage:
  python3 capture_spectral.py
  
Commands:
  pic <wavelength>  - Capture and save RAW image as nu_<wavelength>nm.dng (e.g., pic 700)
  quit              - Exit the program
  help              - Show this help message
"""

import os
import time
from datetime import datetime

try:
    from picamera2 import Picamera2
except Exception as e:
    raise SystemExit("picamera2 non trouvé. Ce script doit s'exécuter sur Raspberry Pi avec picamera2.")

import numpy as np


def configure_camera(picam2, exposure_us=5000, analogue_gain=1.0):
    """Configure camera in manual mode with RAW stream."""
    camera_config = picam2.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)},
        raw={"format": "SBGGR10", "size": (3280, 2464)}
    )
    camera_config["controls"] = {
        "AwbEnable": 0,
        "AnalogueGain": analogue_gain,
        "AnalogueGainMode": 0,
        "ExposureTimeMode": 0,
        "AeEnable": 0,
        "AeFlickerMode": 0,
        "ExposureTime": int(exposure_us),
        "FrameDurationLimits": (250000, 250000),  # 250 ms
        "ColourTemperature": 5500,
    }
    picam2.configure(camera_config)


def main():
    print("=" * 70)
    print("Spectral Photo Capture Tool")
    print("=" * 70)
    
    # Create experiment folder
    out_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    photos_dir = os.path.join(out_dir, f'spectral_photos_{timestamp}')
    os.makedirs(photos_dir, exist_ok=True)
    
    print(f"\nPhotos will be saved to: {photos_dir}\n")
    
    # Initialize camera
    print("Initializing camera...")
    exposure_us = 1000  # Fixed exposure time (20 ms)
    picam2 = Picamera2()
    configure_camera(picam2, exposure_us=exposure_us, analogue_gain=1.0)
    picam2.start()
    time.sleep(0.5)
    
    # Stabilize with a few frames
    for _ in range(3):
        req = picam2.capture_request()
        req.release()
    time.sleep(0.2)
    
    print("Camera ready!\n")
    print(f"Fixed exposure time: {exposure_us} µs ({exposure_us/1000:.1f} ms)")
    print("\nCommands:")
    print("  pic <wavelength>  - Capture photo (e.g., pic 700 for 700nm)")
    print("  quit              - Exit")
    print("  help              - Show help\n")
    
    photo_count = 0
    
    while True:
        try:
            user_input = input(">> ").strip()
            
            if not user_input:
                continue
            
            # Parse command
            parts = user_input.split()
            command = parts[0].lower()
            
            if command == 'quit':
                print("Exiting...")
                break
            
            elif command == 'help':
                print("\nSpectral Photo Capture Tool (RAW/DNG)")
                print("  pic <wavelength>  - Capture and save RAW photo as nu_<wavelength>nm.dng")
                print("                      Example: pic 700")
                print("  quit              - Exit the program")
                print("  help              - Show this help\n")
            
            elif command == 'pic':
                if len(parts) < 2:
                    print("✗ Usage: pic <wavelength>")
                    print("  Example: pic 700")
                    continue
                
                try:
                    wavelength = float(parts[1])
                    
                    # Capture RAW image
                    print(f"Capturing photo at {wavelength}nm...", end=" ", flush=True)
                    req = picam2.capture_request()
                    
                    # Get metadata to verify exposure time
                    meta = req.get_metadata()
                    actual_exposure = float(meta.get('ExposureTime', exposure_us))
                    
                    # Save as DNG (RAW format)
                    photo_filename = f'nu_{wavelength:.0f}nm.dng'
                    photo_path = os.path.join(photos_dir, photo_filename)
                    req.save_dng(photo_path)
                    req.release()
                    
                    photo_count += 1
                    print(f"✓ Saved as {photo_filename} (exp: {actual_exposure:.0f} µs)")
                    
                except ValueError:
                    print(f"✗ Invalid wavelength: {parts[1]}")
                    print("  Please provide a numeric value (e.g., pic 700)")
            
            else:
                print(f"✗ Unknown command: {command}")
                print("  Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...")
            break
        except Exception as e:
            print(f"✗ Error: {e}")
    
    picam2.stop()
    print(f"\n{photo_count} photo(s) captured and saved to:")
    print(f"  {photos_dir}")


if __name__ == '__main__':
    main()
