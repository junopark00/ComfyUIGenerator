import urllib.request
import os

THREEJS_URL = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"
GLTFLOADER_URL = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"
MODULES_DIR = os.path.dirname(__file__)

for url, fname in [
    (THREEJS_URL, "three.min.js"),
    (GLTFLOADER_URL, "GLTFLoader.js")
]:
    out_path = os.path.join(MODULES_DIR, fname)
    print(f"Downloading {url} -> {out_path}")
    urllib.request.urlretrieve(url, out_path)
print("Done.")
