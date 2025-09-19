import os
import json
import httpx
import mimetypes
import traceback
import asyncio
import shutil
from io import BytesIO
from PIL import Image
from random import randint

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from qasync import QEventLoop, asyncSlot
import qdarktheme

from modules import dragdrop_label
from modules import threejs_viewer
from modules import constants


def get_unique_filename(directory: str, filename: str) -> str:
    """
    Generate a unique filename in the given directory to avoid conflicts.
    Uses OS-appropriate naming conventions:
    - Windows: filename (1).ext, filename (2).ext, etc.
    - Unix/Linux/macOS: filename_1.ext, filename_2.ext, etc.
    """
    if not os.path.exists(os.path.join(directory, filename)):
        return filename
    
    name, ext = os.path.splitext(filename)
    counter = 1
    
    # Use Windows-style naming on Windows, Unix-style on others
    if os.name == 'nt':  # Windows
        while True:
            new_filename = f"{name} ({counter}){ext}"
            if not os.path.exists(os.path.join(directory, new_filename)):
                return new_filename
            counter += 1
    else:  # Unix/Linux/macOS
        while True:
            new_filename = f"{name}_{counter}{ext}"
            if not os.path.exists(os.path.join(directory, new_filename)):
                return new_filename
            counter += 1
            
def load_fonts() -> None:
    font_dir = os.path.join(os.path.dirname(__file__), constants.FONT_DIR)
    if not os.path.exists(font_dir):
        return
    try:
        installed_fonts = set(QFontDatabase().families())

        for entry in os.scandir(font_dir):
            if not (entry.is_file() and entry.name.lower().endswith((".ttf", ".otf"))):
                continue
            font_path = entry.path

            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id == -1:
                continue
            
            for family in QFontDatabase.applicationFontFamilies(font_id):
                if family not in installed_fonts:
                    pass
    except Exception:
        print("Error loading fonts:", traceback.format_exc())
load_fonts()

class ComfyClient:
    def __init__(self, api_url, log_path):
        self.api_url = api_url
        self.log_path = log_path

    async def queue_prompt(self, client, workflow: dict, timeout: float = 30.0) -> str:
        res = await client.post(f"{self.api_url}/prompt", json={"prompt": workflow}, timeout=timeout)
        res.raise_for_status()
        return res.json().get("prompt_id")

    async def wait_for_completion(self, client, prompt_id: str, log_callback, timeout: float = 30.0):
        while True:
            try:
                queue_res = await client.get(f"{self.api_url}/queue", timeout=timeout)
                queue_res.raise_for_status()
                queue_data = queue_res.json()

                active = queue_data.get("queue_running", []) + queue_data.get("queue_pending", [])
                if not any(item[1] == prompt_id for item in active if isinstance(item, list) and len(item) > 1):
                    break
            except Exception as e:
                log_callback(f"[Connection Error] {str(e)}")
                # Continue trying instead of failing immediately
                pass

            if os.path.exists(self.log_path):
                try:
                    with open(self.log_path, "rb") as f:
                        f.seek(-1024, os.SEEK_END)
                        last_lines = f.read().decode(errors="ignore").splitlines()
                        if last_lines:
                            last_line = last_lines[-1].strip()
                            if last_line:
                                log_callback(last_line)
                except Exception as e:
                    log_callback(f"[Log Read Error] {str(e)}")

            await asyncio.sleep(0.5)

    async def get_history(self, client, prompt_id: str, timeout: float = 30.0):
        res = await client.get(f"{self.api_url}/history/{prompt_id}", timeout=timeout)
        res.raise_for_status()
        return res.json().get(prompt_id)

    async def get_image_url(self, outputs: dict) -> str:
        for node_output in outputs.values():
            if "images" in node_output:
                for image in node_output["images"]:
                    filename = image.get("filename")
                    subfolder = image.get("subfolder", "")
                    if filename:
                        return f"{self.api_url}/view?filename={filename}&subfolder={subfolder}&type=output", filename
        return None, None
    
    async def get_mesh_paths(self, outputs: dict) -> list:
        mesh_paths = []
        for node_output in outputs.values():
            # obj
            if isinstance(node_output, dict) and 'result' in node_output:
                result = node_output['result']
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, str) and (item.endswith('.obj') or item.endswith('.glb')):
                            mesh_paths.append(item)
                elif isinstance(result, str) and (result.endswith('.obj') or result.endswith('.glb')):
                    mesh_paths.append(result)
        return list(map(lambda x: f"{constants.COMFY_OUTPUT_DIR}/{x}", mesh_paths))

    async def download_image(self, client, url: str, timeout: float = 30.0) -> bytes:
        res = await client.get(url, timeout=timeout)
        res.raise_for_status()
        return res.content


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.set_vars()
        self.create_widgets()
        self.create_layout()
        self.connections()
        qdarktheme.setup_theme()
        self.setStyleSheet('''
            QWidget {
                font-family: "Lato Black";
                font-weight: bold;
                font-size: 12px;
                }
            QToolTip {
                background-color: #232629;
                color: #f0f0f0;
                border: 1px solid #444;
                font-family: "Lato Black";
                font-size: 12px;
                border-radius: 6px;
            }
        ''')
        self.resize(1000, 500)

    def set_vars(self):
        self.constants = constants
        self.log_path = "W:/MTHD_core/AI/logs/comfyui.log"
        self.client = ComfyClient(self.constants.COMFY_API_URL, self.log_path)
        self.mode = "text2image"
        self.last_log_line = ""
        self.image_path = ""

    def create_widgets(self):
        self.setWindowTitle("ComfyUI Generator")
        self.setMinimumSize(1000, 500)
        self.mode_cmbx = QComboBox()
        self.mode_cmbx.addItems([
            "text2image",
            "image2mesh",
        ])
        self.save_path_input = QLineEdit(placeholderText="path/to/save/folder")
        self.save_path_input.setText(os.path.expanduser("~/Downloads").replace(os.sep, "/"))
        self.browse_button = QPushButton("...")
        self.browse_button.setFixedWidth(30)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_text.setPlaceholderText("Logs will appear here...")
        self.log_text.setTextColor(QColor(200, 200, 200))
        self.log_text.setFixedHeight(100)
        
        self.generate_button = QPushButton("Generate")
        
        self.txt2img_group = QGroupBox("Text to Image")
        self.txt2img_prompt = QTextEdit(placeholderText="Enter your prompt here")
        
        self.txt2img_sampler = QComboBox()
        self.txt2img_sampler.addItems(self.constants.COMFY_TXT2IMG_SAMPLERS)
        self.txt2img_sampler.setCurrentText("euler")
        self.txt2img_sampler.setMinimumHeight(28)
        self.txt2img_sampler.setToolTip(
            """The sampler to use for the diffusion process.
Different samplers can affect the quality and style of the generated images."""
            )
        
        self.txt2img_guidance = QDoubleSpinBox()
        self.txt2img_guidance.setMinimumHeight(28)
        self.txt2img_guidance.setRange(0.0, 100.0)
        self.txt2img_guidance.setSingleStep(0.1)
        self.txt2img_guidance.setValue(3.5)
        self.txt2img_guidance.setToolTip(
            """How strongly the model should follow the prompt.
Higher values mean more adherence to the prompt."""
            )
        self.txt2img_scheduler = QComboBox()
        self.txt2img_scheduler.setMinimumHeight(28)
        self.txt2img_scheduler.addItems(self.constants.COMFY_TXT2IMG_SCHEDULERS)
        self.txt2img_scheduler.setCurrentText("simple")
        self.txt2img_scheduler.setToolTip(
            """The scheduler to use for the diffusion process.
Different schedulers can affect the quality and style of the generated images."""
            )
        
        self.txt2img_steps = QSpinBox()
        self.txt2img_steps.setMinimumHeight(28)
        self.txt2img_steps.setRange(1, 100)
        self.txt2img_steps.setValue(20)
        self.txt2img_steps.setToolTip(
            """The number of diffusion steps to take.
More steps can lead to higher quality images, but also increase generation time."""
            )
        
        self.txt2img_random_noise = QCheckBox()
        self.txt2img_random_noise.setChecked(True)
        self.txt2img_random_noise.setToolTip(
            """Enable to use a random noise seed for generation.
If disabled, a fixed noise seed will be used."""
            )
        
        self.txt2img_noise = QLineEdit()
        self.txt2img_noise.setMinimumHeight(28)
        self.txt2img_noise.setDisabled(True)
        self.txt2img_noise.setValidator(QIntValidator(0, 100000000, self))
        self.txt2img_noise.setText(str(randint(0, 100000000)))
        self.txt2img_noise.setToolTip(
            """The noise seed to use for generation."""
            )
        
        self.img2mesh_group = QGroupBox("Image to Mesh")
        self.img2mesh_group.hide()
        self.dragdrop_label = dragdrop_label.DragDropLabel(self)
        
        self.img2mesh_guidance_scale = QDoubleSpinBox()
        self.img2mesh_guidance_scale.setMinimumHeight(28)
        self.img2mesh_guidance_scale.setRange(0.0, 100.0)
        self.img2mesh_guidance_scale.setSingleStep(0.1)
        self.img2mesh_guidance_scale.setValue(5.5)
        self.img2mesh_guidance_scale.setToolTip(
            """How strongly the model should follow the prompt.
Higher values mean more adherence to the prompt."""
        )
        
        self.img2mesh_steps = QSpinBox()
        self.img2mesh_steps.setMinimumHeight(28)
        self.img2mesh_steps.setRange(1, 2048)
        self.img2mesh_steps.setValue(50)
        self.img2mesh_steps.setToolTip(
            """The number of steps for the diffusion process.
More steps can lead to higher quality images, but also increase generation time."""
        )
        
        self.img2mesh_max_facenum = QLineEdit()
        self.img2mesh_max_facenum.setValidator(QIntValidator(1, 1000000, self))
        self.img2mesh_max_facenum.setText("50000")
        self.img2mesh_max_facenum.setToolTip(
            """Maximum number of faces for the generated mesh.
This can help control the complexity of the mesh, 
but too large values may lead to performance issues."""
        )
        
        self.img2mesh_apply_delight = QCheckBox()
        self.img2mesh_apply_delight.setChecked(False)
        self.img2mesh_apply_delight.setToolTip(
            """Enabling this option applies the Delight algorithm, which improves the quality of the texture.
However, the mesh quality may be reduced."""
        )
        
        self.image_label = QLabel()
        self.image_label.setStyleSheet("background-color: black;")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        
        self.glb_viewer = threejs_viewer.ThreeJSGLBViewer()
        self.glb_viewer.show()

    def create_layout(self):
        self.main_layout = QHBoxLayout()
        self.sub_layout2 = QVBoxLayout()
        
        self.sub_layout = QFormLayout()
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_cmbx)
        mode_layout.addStretch()
        
        self.sub_layout.addRow("Mode", mode_layout)
        self.sub_layout.addRow(QLabel())
        
        txt2img_options_layout = QFormLayout()
        txt2img_options_layout.addRow("Prompt", self.txt2img_prompt)
        sampler_layout = QHBoxLayout()
        sampler_layout.addWidget(self.txt2img_sampler)
        sampler_layout.addStretch()
        txt2img_options_layout.addRow("Sampler", sampler_layout)
        
        guidance_layout = QHBoxLayout()
        guidance_layout.addWidget(self.txt2img_guidance)
        guidance_layout.addStretch()
        txt2img_options_layout.addRow("Guidance", guidance_layout)
        
        scheduler_layout = QHBoxLayout()
        scheduler_layout.addWidget(self.txt2img_scheduler)
        scheduler_layout.addStretch()
        txt2img_options_layout.addRow("Scheduler", scheduler_layout)
        
        steps_layout = QHBoxLayout()
        steps_layout.addWidget(self.txt2img_steps)
        steps_layout.addStretch()
        txt2img_options_layout.addRow("Steps", steps_layout)
        
        noise_layout = QHBoxLayout()
        noise_layout.addWidget(self.txt2img_random_noise)
        noise_layout.addWidget(self.txt2img_noise)
        noise_layout.addStretch()
        txt2img_options_layout.addRow("Random Noise", noise_layout)
        self.txt2img_group.setLayout(txt2img_options_layout)
        self.sub_layout.addRow(self.txt2img_group)
        
        img2mesh_options_layout = QFormLayout()
        img2mesh_options_layout.addRow(self.dragdrop_label)
        
        img2mesh_guidance_layout = QHBoxLayout()
        img2mesh_guidance_layout.addWidget(self.img2mesh_guidance_scale)
        img2mesh_guidance_layout.addStretch()
        img2mesh_options_layout.addRow("Guidance Scale", img2mesh_guidance_layout)
        
        img2mesh_steps_layout = QHBoxLayout()
        img2mesh_steps_layout.addWidget(self.img2mesh_steps)
        img2mesh_steps_layout.addStretch()
        img2mesh_options_layout.addRow("Steps", img2mesh_steps_layout)
        
        img2mesh_max_facenum_layout = QHBoxLayout()
        img2mesh_max_facenum_layout.addWidget(self.img2mesh_max_facenum)
        img2mesh_max_facenum_layout.addStretch()
        img2mesh_options_layout.addRow("Max Face Num", img2mesh_max_facenum_layout)
        
        img2mesh_apply_delight_layout = QHBoxLayout()
        img2mesh_apply_delight_layout.addWidget(self.img2mesh_apply_delight)
        img2mesh_apply_delight_layout.addStretch()
        img2mesh_options_layout.addRow("Apply Delight", img2mesh_apply_delight_layout)
        
        self.img2mesh_group.setLayout(img2mesh_options_layout)
        self.sub_layout.addRow(self.img2mesh_group)
        
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.save_path_input)
        save_layout.addWidget(self.browse_button)
        self.sub_layout.addRow("Output Dir", save_layout)
        self.sub_layout.addRow(QLabel())
        
        self.sub_layout.addRow(self.generate_button)
        
        self.sub_layout.addRow(self.log_text)
        
        self.stack = QStackedLayout()
        self.stack.addWidget(self.image_label)
        self.stack.addWidget(self.glb_viewer)
        self.sub_layout2.addLayout(self.stack)
        
        self.main_layout.addLayout(self.sub_layout)
        self.main_layout.addLayout(self.sub_layout2)
        
        self.setLayout(self.main_layout)

    def connections(self):
        self.browse_button.clicked.connect(self.on_browse)
        self.generate_button.clicked.connect(self.on_generate)
        self.mode_cmbx.currentTextChanged.connect(self.on_mode_change)
        self.dragdrop_label.file_dropped.connect(self.on_drop_image)
        self.txt2img_random_noise.stateChanged.connect(
            lambda: self.txt2img_noise.setDisabled(self.txt2img_random_noise.isChecked())
        )

    def on_browse(self):
        default_folder = self.save_path_input.text() or os.path.expanduser("~/Downloads")
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder", default_folder)
        if folder:
            self.save_path_input.setText(folder)
            
    def on_drop_image(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Error", "The dropped file does not exist.")
            return

        mimetype = mimetypes.guess_type(file_path)[0]
        if not mimetype or not mimetype.startswith("image/"):
            QMessageBox.warning(self, "Invalid File Type", "Please drop a valid image file.")
            return

        label_size = self.dragdrop_label.size()
        pixmap = QPixmap(file_path).scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.dragdrop_label.setPixmap(pixmap)
        self.image_path = file_path

    @asyncSlot()
    async def on_generate(self):
        if self.mode == "text2image":
            if not self.txt2img_prompt.toPlainText().strip():
                QMessageBox.warning(self, "Input Error", "Please enter a prompt.")
                return
            self.image_label.setText("Generating...")
            timeout = 60.0
            
        elif self.mode == "image2mesh":
            if not self.image_path:
                QMessageBox.warning(self, "Input Error", "Please drop an image file.")
                return
            timeout = 300.0
            
        if not self.save_path_input.text():
            QMessageBox.warning(self, "Input Error", "Please select a save folder.")
            return
        
        os.makedirs(self.save_path_input.text(), exist_ok=True)
        
        self.generate_button.setEnabled(False)
        
        if self.txt2img_random_noise.isChecked():
            self.txt2img_noise.setText(str(randint(0, 100000000)))

        try:
            workflow = self.build_workflow()
            # Use longer timeout for mesh generation
            async with httpx.AsyncClient(timeout=timeout) as session:
                prompt_id = await self.client.queue_prompt(session, workflow, timeout)
                if not prompt_id:
                    self.image_label.setText("No prompt_id returned.")
                    self.generate_button.setEnabled(True)
                    return

                self.append_info_log(f"Started generation with prompt_id: {prompt_id}")
                self.append_processing_log(f"Using timeout: {timeout}s")
                
                await self.client.wait_for_completion(session, prompt_id, self.append_processing_log, timeout)

                result = await self.client.get_history(session, prompt_id, timeout)
                if not result:
                    self.image_label.setText("Invalid history result.")
                    self.generate_button.setEnabled(True)
                    return

                if self.mode == "text2image":
                    outputs = result.get("outputs", {})
                    url, filename = await self.client.get_image_url(outputs)
                    if not url:
                        self.image_label.setText("Image filename not found.")
                        self.generate_button.setEnabled(True)
                        return

                    image_data = await self.client.download_image(session, url, timeout)
                    pixmap = self.bytes_to_pixmap(image_data)
                    
                    # Handle duplicate filenames with OS-appropriate naming
                    unique_filename = get_unique_filename(self.save_path_input.text(), filename)
                    save_path = os.path.join(self.save_path_input.text(), unique_filename)
                    pixmap.save(save_path, "PNG", quality=100)
                    
                    self.append_info_log(f"Image saved as: {unique_filename}")
                    self.image_label.setPixmap(
                        pixmap.scaled(
                            512, 512, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        )
                elif self.mode == "image2mesh":
                    outputs = result.get("outputs", {})
                    output_paths = await self.client.get_mesh_paths(outputs)
                    if not output_paths:
                        self.image_label.setText("No mesh files found in outputs.")
                        self.generate_button.setEnabled(True)
                        return
                    glb_path = ""
                    for mesh_path in output_paths:
                        # Handle duplicate filenames with OS-appropriate naming
                        original_filename = os.path.basename(mesh_path)
                        unique_filename = get_unique_filename(self.save_path_input.text(), original_filename)
                        destination_path = os.path.join(self.save_path_input.text(), unique_filename)
                        
                        shutil.copy2(mesh_path, destination_path)
                        self.append_info_log(f"Mesh file saved as: {unique_filename}")
                        
                        if mesh_path.endswith(".glb"):
                            glb_path = mesh_path
                    if glb_path:
                        self.glb_viewer.load_model(glb_path)

        except httpx.ReadTimeout:
            error_msg = f"Request timed out after {timeout}s. The server may be overloaded or the task is taking longer than expected."
            self.image_label.setText(error_msg)
            self.append_error_log(error_msg)
            self.generate_button.setEnabled(True)
        except httpx.ConnectTimeout:
            error_msg = "Connection timed out. Please check if the server is running and accessible."
            self.image_label.setText(error_msg)
            self.append_error_log(error_msg)
            self.generate_button.setEnabled(True)
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            self.image_label.setText(f"HTTP Error: {e.response.status_code}")
            self.append_error_log(error_msg)
            self.generate_button.setEnabled(True)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.image_label.setText(error_msg)
            self.append_error_log(error_msg)
            self.generate_button.setEnabled(True)
            traceback.print_exc()
        finally:
            self.append_info_log("Generation completed.")
            self.generate_button.setEnabled(True)

    def append_processing_log(self, message: str):
        if message != self.last_log_line:
            self.last_log_line = message
            previous_color = self.log_text.textColor()
            self.log_text.setTextColor(QColor(200, 200, 200))
            self.log_text.append(f"[Processing] {message}")
            self.log_text.setTextColor(previous_color)
            
    def append_error_log(self, message: str):
        if message != self.last_log_line:
            self.last_log_line = message
            previous_color = self.log_text.textColor()
            self.log_text.setTextColor(QColor(255, 0, 0))
            self.log_text.append(f"[Error] {message}")
            self.log_text.setTextColor(previous_color)
            
    def append_info_log(self, message: str):
        if message != self.last_log_line:
            self.last_log_line = message
            previous_color = self.log_text.textColor()
            self.log_text.setTextColor(QColor(0, 255, 0))
            self.log_text.append(f"[Info] {message}")
            self.log_text.setTextColor(previous_color)

    def build_workflow(self) -> dict:
        if self.mode == "text2image":
            workflow_name = self.mode_cmbx.currentText()
        elif self.mode == "image2mesh":
            workflow_name = "image2mesh"
            if self.img2mesh_apply_delight.isChecked():
                workflow_name += "_delight"
        path = os.path.join(os.path.dirname(__file__), f"workflows/{self.mode_cmbx.currentText()}.json")
        with open(path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        if self.mode == "text2image":
            text = self.txt2img_prompt.toPlainText().strip()
            sampler = self.txt2img_sampler.currentText()
            guidance = self.txt2img_guidance.value()
            scheduler = self.txt2img_scheduler.currentText()
            steps = self.img2mesh_steps.value()
            noise = self.txt2img_noise.text()
            workflow["294"]["inputs"]["text"] = str(text)
            workflow["287"]["inputs"]["sampler_name"] = str(sampler)
            workflow["291"]["inputs"]["guidance"] = int(guidance)
            workflow["288"]["inputs"]["scheduler"] = str(scheduler)
            workflow["288"]["inputs"]["steps"] = int(steps)
            workflow["290"]["inputs"]["noise_seed"] = int(noise)
            workflow["299"]["inputs"]["filename_prefix"] = self.constants.TXT2IMG_IMAGE_PREFIX
        elif self.mode == "image2mesh":
            image = self.image_path
            guidance_scale = self.img2mesh_guidance_scale.value()
            steps = self.img2mesh_steps.value()
            max_facenum = self.img2mesh_max_facenum.text()
            shutil.copy2(image, self.constants.COMFY_INPUT_DIR)
            workflow["4"]["inputs"]["image"] = os.path.basename(image)
            workflow["205"]["inputs"]["guidance_scale"] = float(guidance_scale)
            workflow["205"]["inputs"]["steps"] = int(steps)
            workflow["217"]["inputs"]["max_facenum"] = int(max_facenum)
            workflow["232"]["inputs"]["filename_prefix"] = self.constants.IMG2MESH_GLB_PREFIX
            workflow["202"]["inputs"]["filename_prefix"] = self.constants.IMG2MESH_OBJ_PREFIX
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")
        return workflow

    def bytes_to_pixmap(self, data: bytes) -> QPixmap:
        image = Image.open(BytesIO(data)).convert("RGBA")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")
        return pixmap
    
    def on_mode_change(self, mode: str):
        self.mode = mode
        if mode == "text2image":
            self.txt2img_group.show()
            self.image_label.show()
            self.img2mesh_group.hide()
            self.stack.setCurrentWidget(self.image_label)
        elif mode == "image2mesh":
            self.txt2img_group.hide()
            self.image_label.hide()
            self.img2mesh_group.show()
            self.stack.setCurrentWidget(self.glb_viewer)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    font = QFont("Lato Black")
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()
