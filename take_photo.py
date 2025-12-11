from picamera2 import Picamera2
from libcamera import controls
import time
import os

picam2 = Picamera2()

# Afficher les propriétés de la caméra
#print("=== PROPRIÉTÉS DE LA CAMÉRA ===")
#print(f"Modèle: {picam2.camera_properties.get('Model', 'N/A')}")
#print(f"Taille du capteur: {picam2.camera_properties.get('PixelArraySize', 'N/A')}")

# Créer la configuration avec RAW
# Le format RAW natif de l'IMX219 est SBGGR10 (Bayer RGGB 10-bit)
camera_config = picam2.create_preview_configuration(
    main={"format": 'XRGB8888', "size": (640, 480)},
    raw={"format": "SBGGR10", "size": (3280, 2464)}
)
# Appliquer des contrôles par défaut dans la configuration permet
# de forcer des modes avant que la caméra ne démarre.
camera_config["controls"] = {
    "AwbEnable": 0,
    "AnalogueGain": 1.0,
    "AnalogueGainMode": 0,
    "ExposureTimeMode": 0,
    "AeEnable": 0,
    # Valeur en microsecondes (50000 = 50 ms)
    "ExposureTime": 10000,
    "ColourTemperature": 5500,
}
picam2.configure(camera_config)

# Afficher les paramètres disponibles
#print("\n=== PARAMÈTRES DE CONTRÔLE DISPONIBLES ===")
controls_available = picam2.camera_controls
control_dict = {}
for ctrl_id in controls_available:
    # Récupérer le nom via la représentation
    ctrl_str = str(ctrl_id)
    # Extraire le nom entre parenthèses
    if "'" in ctrl_str:
        ctrl_name = ctrl_str.split("'")[1]
    else:
        ctrl_name = str(ctrl_id)
    control_dict[ctrl_name] = ctrl_id
    #print(f"- {ctrl_name}")

# Afficher la liste des contrôles récupérés (utile pour debugging)
print("\n=== CONTROLES DISPONIBLES (extraits) ===")
for name in sorted(control_dict.keys()):
    print(f"- {name}")

# Debug: inspect certains contrôles pour connaître leurs attributs (aide au mapping des enums)
for probe in ('AeEnable', 'ExposureTimeMode', 'AnalogueGainMode', 'AeExposureMode', 'AeConstraintMode'):
    if probe in control_dict:
        ctrl = control_dict[probe]
        try:
            print(f"\n-- Inspect {probe}: {repr(ctrl)}")
            print('attrs:', [a for a in dir(ctrl) if not a.startswith('_')])
        except Exception as e:
            print(f"Erreur introspection {probe}: {e}")

picam2.start()
time.sleep(0.2)

# Fonction pour modifier un paramètre
def set_camera_param(param_name, value):
    """Modifie un paramètre de la caméra"""
    try:
        # Chercher le contrôle correspondant
        matching = [n for n in control_dict.keys() if param_name.lower() in n.lower()]
        
        if not matching:
            print(f"✗ Paramètre '{param_name}' non trouvé")
            return False
            
        control_name = matching[0]
        ctrl_id = control_dict[control_name]
        picam2.set_controls({ctrl_id: value})
        print(f"✓ {control_name} = {value}")
        return True
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False

# Fonction pour lire les paramètres courants
def get_camera_params():
    """Affiche tous les paramètres courants"""
    print("\n=== PARAMÈTRES COURANTS ===")
    metadata = picam2.capture_metadata()
    for key, value in sorted(metadata.items()):
        if isinstance(value, tuple):
            print(f"{key}: {value[:3]}...")
        else:
            print(f"{key}: {value}")


# Afficher les paramètres après modification
get_camera_params()

# Capturer l'image en RAW
print("\n=== CAPTURE RAW ===")
# Capture au format RAW (données brutes du capteur)
request = picam2.capture_request()
# Sauvegarder le fichier RAW en format DNG dans le dossier du script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(script_dir, exist_ok=True)
out_path = os.path.join(script_dir, "photo_raw.dng")
request.save_dng(out_path)
print(f"✓ Photo RAW capturée: {out_path}")

# Accéder aux données brutes si nécessaire
raw_data = request.make_array("raw")
print(f"✓ Dimensions des données RAW: {raw_data.shape}")
print(f"✓ Type de données: {raw_data.dtype}")
print(f"✓ Valeurs min/max: {raw_data.min()} - {raw_data.max()}")

request.release()
print("\n✓ Capture terminée!")
