# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QColor
import os

THREEJS_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>3D Viewer (three.js)</title>
    <style>
        html, body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: #000000;
        }
        canvas {
            display: block;
            will-change: transform;
        }
    </style>
    <script src="three.min.js"></script>
    <script src="GLTFLoader.js"></script>
    <script src="OBJLoader.js"></script>
    <script src="FBXLoader.js"></script>
    <script src="fflate.min.js"></script>
    <script src="OrbitControls.js"></script>
</head>
<style>
  #mode-menu {
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
  }
  #mode-main-btn {
    background: rgba(0,0,0,0.7);
    border-radius: 4px;
    border: 1.5px solid #444;
    padding: 8px;
    cursor: pointer;
    outline: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
  }
  #mode-main-btn img {
    width: 28px;
    height: 28px;
    display: block;
  }
  .mode-btn-list {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: none;
    max-height: 0;
    overflow: hidden;
    opacity: 0;
    transform: translateY(-20px);
    transition: max-height 0.35s cubic-bezier(.4,0,.2,1), opacity 0.25s, transform 0.35s cubic-bezier(.4,0,.2,1);
    pointer-events: none;
  }
  .mode-btn-list.show {
    max-height: 500px;
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
    transition: max-height 0.45s cubic-bezier(.4,0,.2,1), opacity 0.25s, transform 0.45s cubic-bezier(.4,0,.2,1);
  }
  .mode-btn {
    background: rgba(0,0,0,0.7);
    border-radius: 4px;
    border: 1.5px solid #444;
    color: #fff;
    font-size: 14px;
    padding: 6px 16px;
    cursor: pointer;
    outline: none;
    transition: background 0.2s;
    min-width: 90px;
    text-align: left;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  .mode-btn:hover {
    background: rgba(40,40,40,0.85);
  }
</style>
<div id="mode-menu">
  <div style="display: flex; flex-direction: row; align-items: center; gap: 8px;">
    <button id="mode-main-btn" title="View Modes">
      <img src="../../source/icon/box.svg" alt="mode" />
    </button>
    <button id="grid-toggle-btn" title="Toggle Grid" style="background: rgba(0,0,0,0.7); border-radius: 4px; border: 1.5px solid #444; padding: 8px; cursor: pointer; outline: none; box-shadow: 0 2px 8px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center; width: 44px; height: 44px;">
      <img id="grid-toggle-icon" src="../../source/icon/grid-2x2.svg" alt="grid" style="width: 28px; height: 28px; display: block; filter: brightness(1); transition: filter 0.2s;" />
    </button>
  </div>
  <div class="mode-btn-list" id="mode-btn-list">
    <button class="mode-btn" onclick="setViewMode('original')">Original</button>
    <button class="mode-btn" onclick="setViewMode('mesh')">Mesh</button>
    <button class="mode-btn" onclick="setViewMode('normal')">Normal</button>
    <button class="mode-btn" onclick="setViewMode('wireframe')">Wireframe</button>
  </div>
</div>
<script>
  const mainBtn = document.getElementById('mode-main-btn');
  const btnList = document.getElementById('mode-btn-list');
  mainBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    btnList.classList.toggle('show');
  });
  const gridBtn = document.getElementById('grid-toggle-btn');
  const gridIcon = document.getElementById('grid-toggle-icon');
  let gridEnabled = true;
  let gridUnit = 'm';

  gridBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!gridEnabled) {
      gridEnabled = true;
      gridUnit = 'm';
      gridIcon.src = '../../source/icon/grid-2x2.svg';
      setGridVisible(true);
      if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
      if (gridLabelGroup) { scene.remove(gridLabelGroup); gridLabelGroup = null; }
      createGrid(currentModel);
    } else if (gridUnit === 'm') {
      gridUnit = 'cm';
      gridIcon.src = '../../source/icon/grid-3x3.svg';
      if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
      if (gridLabelGroup) { scene.remove(gridLabelGroup); gridLabelGroup = null; }
      createGrid(currentModel);
    } else {
      gridEnabled = false;
      gridIcon.src = '../../source/icon/grid-2x2.svg';
      setGridVisible(false);
    }
    gridBtn.style.filter = gridEnabled ? '' : 'brightness(0.4)';
  });

  let gridHelper = null;
  let gridLabelGroup = null;
  function createGrid(model) {
    if (gridHelper) return;
    let size = 10.0;
    let divisions = 10;
    let labelText = '10m';
    let cellLength = 1.0;
    let cellLabel = '1m';
    if (gridUnit === 'cm') {
      size = 10.0;
      divisions = 100;
      labelText = '1000cm';
      cellLength = 0.1;
      cellLabel = '10cm';
    }
    let gridY = 0;
    if (model) {
      let box = new THREE.Box3().setFromObject(model);
      gridY = box.min.y - 0.01;
    }
    gridHelper = new THREE.GridHelper(size, divisions, 0xcccccc, 0x888888);
    gridHelper.position.y = gridY;
    gridHelper.material.opacity = 0.7;
    gridHelper.material.transparent = true;
    scene.add(gridHelper);

    if (gridLabelGroup) scene.remove(gridLabelGroup);
    gridLabelGroup = new THREE.Group();
    let half = size / 2;
    let spriteX = makeTextSprite(labelText);
    spriteX.position.set(half, gridY + 0.06, -half - 0.18);
    spriteX.material.depthTest = false;
    spriteX.renderOrder = 999;
    gridLabelGroup.add(spriteX);
    let spriteZ = makeTextSprite(labelText);
    spriteZ.position.set(-half - 0.18, gridY + 0.06, half);
    spriteZ.material.depthTest = false;
    spriteZ.renderOrder = 999;
    gridLabelGroup.add(spriteZ);

    let barGroup = new THREE.Group();
    let barY = gridY + 0.03;
    let barZ = -half + cellLength / 2;
    let barX0 = -half;
    let barX1 = -half + cellLength;
    let barGeom = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(barX0, barY, barZ),
      new THREE.Vector3(barX1, barY, barZ)
    ]);
    let barMat = new THREE.LineBasicMaterial({ color: 0x2cdcff, linewidth: 2 });
    barGroup.add(new THREE.Line(barGeom, barMat));
    let arrowSize = 0.05;
    let leftArrow = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(barX0, barY, barZ),
      new THREE.Vector3(barX0 + arrowSize, barY + arrowSize, barZ),
      new THREE.Vector3(barX0, barY, barZ),
      new THREE.Vector3(barX0 + arrowSize, barY - arrowSize, barZ)
    ]);
    let rightArrow = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(barX1, barY, barZ),
      new THREE.Vector3(barX1 - arrowSize, barY + arrowSize, barZ),
      new THREE.Vector3(barX1, barY, barZ),
      new THREE.Vector3(barX1 - arrowSize, barY - arrowSize, barZ)
    ]);
    barGroup.add(new THREE.Line(leftArrow, barMat));
    barGroup.add(new THREE.Line(rightArrow, barMat));
    let barLabel = makeTextSprite(cellLabel);
    barLabel.position.set((barX0 + barX1) / 2, barY + 0.12, barZ);
    barLabel.material.depthTest = false;
    barLabel.renderOrder = 999;
    barGroup.add(barLabel);
    gridLabelGroup.add(barGroup);
    scene.add(gridLabelGroup);
  }
  function setGridVisible(visible) {
    if (gridHelper) gridHelper.visible = visible;
    if (gridLabelGroup) gridLabelGroup.visible = visible;
  }
  function makeTextSprite(message) {
    const canvas = document.createElement('canvas');
    const size = 128;
    canvas.width = size;
    canvas.height = size / 2;
    const ctx = canvas.getContext('2d');
    ctx.font = 'bold 32px Lato, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 6;
    ctx.strokeText(message, size/2, size/4);
    ctx.fillStyle = '#2cdcff';
    ctx.fillText(message, size/2, size/4);
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(0.3, 0.15, 1.0);
    return sprite;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const glbPath = urlParams.get('glb');
  const objPath = urlParams.get('obj');
  const fbxPath = urlParams.get('fbx');

  // Hide 'Original' mode button for non-GLB formats
  function updateModeMenuForFormat() {
    const originalBtn = document.querySelector('.mode-btn[onclick*="original"]');
    if (originalBtn) {
      if (glbPath) {
        originalBtn.style.display = '';
      } else {
        originalBtn.style.display = 'none';
      }
    }
  }
  updateModeMenuForFormat();

  let currentModel = null;
  let originalMaterials = new Map();

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x6c6c6c);
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(0, 0, 2.5);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputEncoding = THREE.sRGBEncoding;
  document.body.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.target.set(0, 0, 0);
  controls.update();

  function setLightsForMode(mode) {
    scene.children = scene.children.filter(obj => !(obj.isLight));
    if (mode === 'original') {
      const light1 = new THREE.DirectionalLight(0xffffff, 1.5);
      light1.position.set(1, 0, 1);
      scene.add(light1);
      const light2 = new THREE.DirectionalLight(0xffffff, 1.5);
      light2.position.set(-1, 0, -1);
      scene.add(light2);
      const light3 = new THREE.DirectionalLight(0xffffff, 0.5);
      light3.position.set(1, 0, -1);
      scene.add(light3);
      const light4 = new THREE.DirectionalLight(0xffffff, 0.5);
      light4.position.set(-1, 0, 1);
      scene.add(light4);
      const ambient = new THREE.AmbientLight(0xffffff, 2.0);
      scene.add(ambient);
    } else {
      const light1 = new THREE.DirectionalLight(0xffffff, 0.3);
      light1.position.set(1, 0, 1);
      scene.add(light1);
      const light2 = new THREE.DirectionalLight(0xffffff, 0.3);
      light2.position.set(-1, 0, -1);
      scene.add(light2);
      const light3 = new THREE.DirectionalLight(0xffffff, 0.1);
      light3.position.set(1, 0, -1);
      scene.add(light3);
      const light4 = new THREE.DirectionalLight(0xffffff, 0.1);
      light4.position.set(-1, 0, 1);
      scene.add(light4);
      const ambient = new THREE.AmbientLight(0xffffff, 0.2);
      scene.add(ambient);
    }
  }

  const meshMaterial = new THREE.MeshLambertMaterial({
    color: 0xcccccc,
    side: THREE.DoubleSide,
    vertexColors: false
  });
  const meshNormalMaterial = new THREE.MeshNormalMaterial({
    side: THREE.DoubleSide
  });

  if (glbPath) {
    const loader = new THREE.GLTFLoader();
    loader.load(glbPath, function(gltf) {
      if (currentModel) scene.remove(currentModel);
      if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
      if (gridLabelGroup) { scene.remove(gridLabelGroup); gridLabelGroup = null; }
      currentModel = gltf.scene;
      scene.add(currentModel);
      originalMaterials.clear();
      currentModel.traverse(function(child) {
        if (child.isMesh) originalMaterials.set(child.uuid, child.material);
      });
      setLightsForMode('original');
      camera.position.set(0, 0, 2.5);
      createGrid(currentModel);
      setGridVisible(true);
      gridEnabled = true;
      gridIcon.style.filter = 'brightness(1)';
      animate();
    }, undefined, function(error) {
      alert('GLB load error: ' + error);
    });
  } else if (objPath) {
    const loader = new THREE.OBJLoader();
    loader.load(objPath, function(obj) {
      if (currentModel) scene.remove(currentModel);
      if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
      if (gridLabelGroup) { scene.remove(gridLabelGroup); gridLabelGroup = null; }
      currentModel = obj;
      scene.add(currentModel);
      originalMaterials.clear();
      currentModel.traverse(function(child) {
        if (child.isMesh) originalMaterials.set(child.uuid, child.material);
      });
      setLightsForMode('mesh');
      camera.position.set(0, 0, 2.5);
      createGrid(currentModel);
      setGridVisible(true);
      gridEnabled = true;
      gridIcon.style.filter = 'brightness(1)';
      animate();
    }, undefined, function(error) {
      alert('OBJ load error: ' + error);
    });
  } else if (fbxPath) {
    const loader = new THREE.FBXLoader();
    loader.load(fbxPath, function(obj) {
      if (currentModel) scene.remove(currentModel);
      if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
      if (gridLabelGroup) { scene.remove(gridLabelGroup); gridLabelGroup = null; }
      currentModel = obj;
      scene.add(currentModel);
      currentModel.traverse(function(child) {
        if (child.isMesh) {
          child.material = new THREE.MeshLambertMaterial({ color: 0xcccccc });
          originalMaterials.set(child.uuid, child.material);
        }
      });
      originalMaterials.clear();
      currentModel.traverse(function(child) {
        if (child.isMesh) originalMaterials.set(child.uuid, child.material);
      });
      setLightsForMode('mesh');
      camera.position.set(0, 0, 2.5);
      createGrid(currentModel);
      setGridVisible(true);
      gridEnabled = true;
      gridIcon.style.filter = 'brightness(1)';
      animate();
    }, undefined, function(error) {
      alert('FBX load error: ' + error);
    });
  } else {
    if (!gridHelper) createGrid(null);
    setGridVisible(true);
  }

  function updateGridLabelScale() {
    if (!gridLabelGroup) return;
    const desiredPixelSize = 48;
    gridLabelGroup.children.forEach(sprite => {
      if (sprite.isSprite) {
        const cam = camera;
        const worldPos = sprite.getWorldPosition(new THREE.Vector3());
        const distance = cam.position.distanceTo(worldPos);
        const vFOV = cam.fov * Math.PI / 180;
        const heightInWorld = 2 * Math.tan(vFOV / 2) * distance;
        const pixelToWorld = heightInWorld / renderer.domElement.height;
        const scale = desiredPixelSize * pixelToWorld;
        sprite.scale.set(scale, scale * 0.5, 1.0);
      } else if (sprite.children) {
        sprite.children.forEach(child => {
          if (child.isSprite) {
            const cam = camera;
            const worldPos = child.getWorldPosition(new THREE.Vector3());
            const distance = cam.position.distanceTo(worldPos);
            const vFOV = cam.fov * Math.PI / 180;
            const heightInWorld = 2 * Math.tan(vFOV / 2) * distance;
            const pixelToWorld = heightInWorld / renderer.domElement.height;
            const scale = desiredPixelSize * pixelToWorld;
            child.scale.set(scale, scale * 0.5, 1.0);
          }
        });
      }
    });
  }

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
    customGizmo.quaternion.copy(camera.quaternion);
    gizmoRenderer.render(gizmoScene, gizmoCamera);
    updateGridLabelScale();
    if (gridLabelGroup) {
      gridLabelGroup.traverse(function(child) {
        if (child.isSprite) {
          child.lookAt(camera.position);
        }
      });
    }
  }

  window.addEventListener('resize', function() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  function setViewMode(mode) {
    if (!currentModel) return;
    setLightsForMode(mode);
    currentModel.traverse(function (child) {
      if (child.isMesh) {
        if (child.geometry && !child.geometry.attributes.normal) {
          child.geometry.computeVertexNormals();
        }
        if (mode === 'original' && originalMaterials.has(child.uuid)) {
          child.material = originalMaterials.get(child.uuid);
        } else if (mode === 'mesh') {
          child.material = meshMaterial;
        } else if (mode === 'normal') {
          child.material = meshNormalMaterial;
        } else if (mode === 'wireframe') {
          child.material = new THREE.MeshBasicMaterial({
            wireframe: true,
            color: 0x2cdcff,
            side: THREE.DoubleSide
          });
        }
      }
    });
  }

  // ===== Custom Gizmo Scene =====
  const gizmoSize = 120;
  const gizmoRenderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
  gizmoRenderer.setSize(gizmoSize, gizmoSize);
  gizmoRenderer.setClearColor(0x000000, 0);
  gizmoRenderer.domElement.style.position = 'absolute';
  gizmoRenderer.domElement.style.left = '10px';
  gizmoRenderer.domElement.style.bottom = '10px';
  gizmoRenderer.domElement.style.zIndex = '100';
  document.body.appendChild(gizmoRenderer.domElement);

  const gizmoScene = new THREE.Scene();
  const gizmoCamera = new THREE.PerspectiveCamera(30, 1, 0.1, 10);
  gizmoCamera.position.set(0, 0, 6);
  gizmoScene.add(gizmoCamera);

  const shaftRadius = 0.035;
  const shaftLength = 0.9;
  const sphereRadius = 0.09;

  function createAxis(color, axis) {
    const material = new THREE.MeshBasicMaterial({ color: color });
    const geometry = new THREE.CylinderGeometry(shaftRadius, shaftRadius, shaftLength, 16);
    const shaft = new THREE.Mesh(geometry, material);
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(sphereRadius, 16, 16), material);
    switch (axis) {
      case 'x':
        shaft.rotation.z = Math.PI / 2;
        shaft.position.x = shaftLength / 2;
        sphere.position.x = shaftLength;
        break;
      case 'y':
        shaft.position.y = shaftLength / 2;
        sphere.position.y = shaftLength;
        break;
      case 'z':
        shaft.rotation.x = Math.PI / 2;
        shaft.position.z = shaftLength / 2;
        sphere.position.z = shaftLength;
        break;
    }
    const group = new THREE.Group();
    group.add(shaft);
    group.add(sphere);
    return group;
  }

  function makeAxisLabel(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    ctx.font = 'bold 72px Lato, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = '#222';
    ctx.shadowBlur = 8;
    ctx.fillStyle = color;
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 8;
    ctx.strokeText(text, 64, 64);
    ctx.shadowBlur = 0;
    ctx.fillText(text, 64, 64);
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(0.5, 0.5, 1.0);
    return sprite;
  }

  const customGizmo = new THREE.Group();
  customGizmo.add(createAxis(0xff0000, 'x'));
  customGizmo.add(createAxis(0x00ff00, 'y'));
  customGizmo.add(createAxis(0x0000ff, 'z'));
  const centerCube = new THREE.Mesh(
    new THREE.BoxGeometry(sphereRadius * 2, sphereRadius * 2, sphereRadius * 2),
    new THREE.MeshBasicMaterial({ color: 0xffffff, opacity: 0.85, transparent: true })
  );
  centerCube.position.set(0, 0, 0);
  customGizmo.add(centerCube);

  const xLabel = makeAxisLabel('X', '#ff6666');
  xLabel.position.set(1.25, 0, 0);
  customGizmo.add(xLabel);
  const yLabel = makeAxisLabel('Y', '#66ff66');
  yLabel.position.set(0, 1.25, 0);
  customGizmo.add(yLabel);
  const zLabel = makeAxisLabel('Z', '#6699ff');
  zLabel.position.set(0, 0, 1.25);
  customGizmo.add(zLabel);

  gizmoScene.add(customGizmo);
</script>
</body>
</html>
'''

class ThreeJSGLBViewer(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page().setBackgroundColor(QColor("#000000"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._threejs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ThreeJS'))
        if not os.path.exists(self._threejs_dir):
            os.makedirs(self._threejs_dir)
        self._ensure_threejs_dependencies()
        self._write_html_file()

    def _ensure_threejs_dependencies(self):
        import urllib.request
        js_libs = [
            ('three.min.js', "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"),
            ('GLTFLoader.js', "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"),
            ('OBJLoader.js', "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/OBJLoader.js"),
            ('FBXLoader.js', "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/FBXLoader.js"),
            ('fflate.min.js', 'https://cdn.jsdelivr.net/npm/fflate@0.8.0/umd/index.min.js'),
            ('OrbitControls.js', 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js'),
        ]
        for fname, url in js_libs:
            dst = os.path.join(self._threejs_dir, fname)
            if not os.path.exists(dst):
                try:
                    urllib.request.urlretrieve(url, dst)
                except Exception as e:
                    print(f"Failed to download {fname}: {e}")

    def _write_html_file(self):
        self._html_path = os.path.join(self._threejs_dir, 'threejs_temp.html')
        with open(self._html_path, 'w', encoding='utf-8') as f:
            f.write(THREEJS_HTML)

    def load_model(self, model_path):
        model_url = 'file:///' + os.path.abspath(model_path).replace('\\', '/')
        ext = os.path.splitext(model_path)[1].lower()
        html_path = self._html_path.replace('\\', '/')
        if ext == '.obj':
            html_url = f'file:///{html_path}?obj={model_url}'
        elif ext == '.fbx':
            html_url = f'file:///{html_path}?fbx={model_url}'
        elif ext in ['.glb', '.gltf']:
            html_url = f'file:///{html_path}?glb={model_url}'
        else:
            raise ValueError(f"Unsupported model format: {ext}.\nSupported formats are: .glb, .gltf, .obj, .fbx.")
        self.load(html_url)