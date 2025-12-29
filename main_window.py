import os
import json
import httpx
import mimetypes
import traceback
import asyncio
import shutil
import time
import uuid
import websockets
from pathlib import Path
from random import randint

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from qasync import QEventLoop, asyncSlot
import qdarktheme
import sys
sys.path.append(os.path.join(os.path.dirname(__file__)))

from modules import dragdrop_label
from modules import threejs_viewer
from modules import constants
from MTHDLib.storage_paths import StoragePaths


class ComfyMonitor(QObject):
    progress_updated = Signal(int, int, str)
    status_updated = Signal(str)
    queue_updated = Signal(int)
    execution_start = Signal(str)
    execution_success = Signal(str)
    node_executing = Signal(str, str) 

    def __init__(self, host, client_id):
        super().__init__()
        self.host = host
        self.client_id = client_id
        clean_host = host.replace("http://", "").replace("https://", "").rstrip("/")
        self.ws_url = f"ws://{clean_host}/ws?clientId={client_id}"
        self.running = True

    async def connect_and_listen(self):
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.status_updated.emit("Connected to ComfyUI Server.")
                    while self.running:
                        msg = await ws.recv()
                        if not isinstance(msg, str): continue
                        
                        data = json.loads(msg)
                        msg_type = data.get('type')
                        payload = data.get('data', {})

                        if msg_type == 'status':
                            status = payload.get('status', {})
                            exec_info = status.get('exec_info', {})
                            queue_remaining = exec_info.get('queue_remaining', 0)
                            self.queue_updated.emit(queue_remaining)

                        elif msg_type == 'execution_start':
                            self.execution_start.emit(payload.get('prompt_id'))

                        elif msg_type == 'executing':
                            node_id = payload.get('node')
                            prompt_id = payload.get('prompt_id')
                            if node_id:
                                # [수정] 노드가 실행될 때 시그널 방출
                                self.node_executing.emit(node_id, prompt_id)
                            else:
                                # node_id가 None이면 해당 프롬프트 완료됨
                                self.execution_success.emit(prompt_id)

                        elif msg_type == 'progress':
                            val = payload.get('value', 0)
                            max_val = payload.get('max', 1)
                            self.progress_updated.emit(val, max_val, "Processing...")

            except Exception as e:
                self.status_updated.emit(f"Connection lost. Retrying... ({e})")
                await asyncio.sleep(5)

    def stop(self):
        self.running = False


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
    def __init__(self, api_url, log_path, client_id):
        self.api_url = api_url
        self.log_path = log_path
        self.client_id = client_id
    
    async def queue_prompt(self, client, workflow: dict, timeout: float = 30.0) -> str:
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }
        res = await client.post(f"{self.api_url}/prompt", json=payload, timeout=timeout)
        res.raise_for_status()
        return res.json().get("prompt_id")

    async def get_queue_info(self, client):
        try:
            res = await client.get(f"{self.api_url}/queue")
            return res.json()
        except:
            return None
        
    async def get_history(self, client, prompt_id: str, timeout: float = 30.0):
        # ... (기존 코드 동일) ...
        res = await client.get(f"{self.api_url}/history/{prompt_id}", timeout=timeout)
        res.raise_for_status()
        return res.json().get(prompt_id)
        
    async def get_image_url(self, outputs: dict) -> str:
        # ... (기존 코드 동일) ...
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
            if isinstance(node_output, dict) and 'result' in node_output:
                result = node_output['result']
                if isinstance(result, list):
                    for item in result:
                        # [수정] 딕셔너리 형태 처리 추가
                        if isinstance(item, dict) and 'filename' in item:
                            filename = item['filename']
                            subfolder = item.get('subfolder', '')
                            # 전체 경로 조합
                            full_path = f"{constants.COMFY_OUTPUT_DIR}/{subfolder}/{filename}".replace("//", "/")
                            if filename.endswith('.glb') or filename.endswith('.obj'):
                                mesh_paths.append(full_path)
                        # 문자열 형태 처리
                        elif isinstance(item, str) and (item.endswith('.obj') or item.endswith('.glb')):
                            mesh_paths.append(f"{constants.COMFY_OUTPUT_DIR}/{item}")
                            
                elif isinstance(result, str) and (result.endswith('.obj') or result.endswith('.glb')):
                    mesh_paths.append(f"{constants.COMFY_OUTPUT_DIR}/{result}")
        return mesh_paths

    async def download_image(self, client, url: str, timeout: float = 30.0) -> bytes:
        res = await client.get(url, timeout=timeout)
        res.raise_for_status()
        return res.content

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


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.client_id = str(uuid.uuid4())
        self.my_current_prompt_id = None
        self.current_workflow_data = {}
        
        self.set_vars()
        self.create_widgets()
        self.create_layout()
        self.connections()
        self.on_mode_change(self.mode)
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
        self.resize(1000, 700)
        
        self.monitor = ComfyMonitor(self.constants.COMFY_API_URL, self.client_id)
        self.connect_monitor_signals()
        
        QTimer.singleShot(0, self.start_monitor)

    def set_vars(self):
        self.constants = constants
        self.log_path = self.constants.COMFY_LOG_PATH
        self.client = ComfyClient(self.constants.COMFY_API_URL, self.log_path, self.client_id)
        self.mode = "Trellis2"
        self.last_log_line = ""
        self.image_path = ""
        
    def connect_monitor_signals(self):
        self.monitor.progress_updated.connect(self.on_progress)
        self.monitor.status_updated.connect(self.append_info_log)
        self.monitor.execution_start.connect(self.on_execution_start)
        self.monitor.queue_updated.connect(self.on_queue_update)
        self.monitor.node_executing.connect(self.on_node_executing)
        
    @asyncSlot()
    async def start_monitor(self):
        await self.monitor.connect_and_listen()

    def create_widgets(self):
        self.setWindowTitle("ComfyUI Generator")
        self.setMinimumSize(1000, 700)
        self.mode_cmbx = QComboBox()
        self.mode_cmbx.addItems([
            # "text2image",
            "Trellis2",
        ])
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_text.setPlaceholderText("Logs will appear here...")
        self.log_text.setTextColor(QColor(200, 200, 200))
        self.log_text.setFixedHeight(100)
        
        self.queue_label = QLabel("Queue: Idle")
        self.queue_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.generate_button = QPushButton("Generate")
     
        self.img2mesh_group = QGroupBox("Image to Mesh")
        self.img2mesh_group.hide()
        self.dragdrop_label = dragdrop_label.DragDropLabel(self)
        self.path_to_image_le = QLineEdit()
        self.path_to_image_le.setPlaceholderText("path/to/image/file")
        self.path_to_image_le.setReadOnly(True)
        self.path_to_image_btn = QPushButton("...")
        self.path_to_image_btn.setFixedWidth(30)
        
        self.path_to_save_le = QLineEdit(placeholderText="path/to/save/folder")
        self.path_to_save_le.setText(StoragePaths().get_drive_from_unc(str(Path(StoragePaths().CC_MAIN) / "show")) + "/")
        self.path_to_save_btn = QPushButton("...")
        self.path_to_save_btn.setFixedWidth(30)
        self.path_to_save_open_btn = QPushButton()
        self.path_to_save_open_btn.setIcon(QIcon.fromTheme("folder-open"))
        self.path_to_save_open_btn.setFixedWidth(30)
        
        self.current_model_path = QLineEdit(placeholderText="path/to/current/model")
        self.current_model_path.setReadOnly(True)
        self.current_model_btn = QPushButton("...")
        
        self.glb_viewer = threejs_viewer.ThreeJSGLBViewer()
        self.glb_viewer.show()

    def create_layout(self):
        self.main_layout = QHBoxLayout()
        self.sub_layout2 = QVBoxLayout()

        self.sub_widget = QWidget()
        self.sub_layout = QFormLayout()
        self.sub_widget.setLayout(self.sub_layout)
        self.sub_widget.setMinimumWidth(500)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_cmbx)
        mode_layout.addStretch()
        
        self.sub_layout.addRow("Mode", mode_layout)
        self.sub_layout.addRow(QLabel())
        
        img2mesh_options_layout = QFormLayout()
        img2mesh_options_layout.addRow(self.dragdrop_label)
        path_to_image_layout = QHBoxLayout()
        path_to_image_layout.addWidget(self.path_to_image_le)
        path_to_image_layout.addWidget(self.path_to_image_btn)
        img2mesh_options_layout.addRow("Path to Image", path_to_image_layout)
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.path_to_save_le)
        save_layout.addWidget(self.path_to_save_btn)
        save_layout.addWidget(self.path_to_save_open_btn)
        img2mesh_options_layout.addRow("Path to Save", save_layout)
        
        self.img2mesh_group.setLayout(img2mesh_options_layout)
        self.sub_layout.addRow(self.img2mesh_group)
        self.sub_layout.addRow(QLabel())
        
        gen_layout = QVBoxLayout()
        gen_layout.addWidget(self.queue_label)
        gen_layout.addWidget(self.generate_button)
        self.sub_layout.addRow(gen_layout)
        
        self.sub_layout.addRow(self.log_text)
        
        self.stack = QStackedLayout()
        path_to_glb_layout = QHBoxLayout()
        path_to_glb_layout.addWidget(self.current_model_path)
        path_to_glb_layout.addWidget(self.current_model_btn)
        self.sub_layout2.addLayout(path_to_glb_layout)
        self.stack.addWidget(self.glb_viewer)
        self.sub_layout2.addLayout(self.stack)
        
        self.main_layout.addWidget(self.sub_widget, 0)
        self.main_layout.addLayout(self.sub_layout2, 1)
        
        self.setLayout(self.main_layout)

    def connections(self):
        self.path_to_save_btn.clicked.connect(self.on_browse)
        self.generate_button.clicked.connect(self.on_generate)
        self.mode_cmbx.currentTextChanged.connect(self.on_mode_change)
        self.dragdrop_label.file_dropped.connect(self.on_drop_image)
        self.path_to_image_btn.clicked.connect(self.on_browse)
        self.path_to_save_open_btn.clicked.connect(self.on_browse)
        self.current_model_btn.clicked.connect(self.on_browse)
      
    def on_browse(self):
        if self.sender() == self.path_to_image_btn:
            default_path = os.path.dirname(self.path_to_image_le.text()) if self.path_to_image_le.text() else os.path.expanduser("~")
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Image File", default_path, "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff)")
            if file_path:
                self.path_to_image_le.setText(file_path)
                self.on_drop_image(file_path)
        elif self.sender() == self.path_to_save_btn:
            default_path = self.path_to_save_le.text() or "V:/"
            path, _ = QFileDialog.getSaveFileName(self, "Select Save Path", default_path, "GLB Files (*.glb);;All Files (*)")
            if path:
                show_path = os.path.join(StoragePaths().get_drive_from_unc(str(Path(StoragePaths().CC_MAIN) / "show")))
                if not path.startswith(show_path):
                    QMessageBox.warning(self, "Invalid Path", f"Please select a path within {show_path}")
                    return
                if not path.lower().endswith(".glb"):
                    path += ".glb"
                self.path_to_save_le.setText(path)
        elif self.sender() == self.path_to_save_open_btn:
            default_path = self.path_to_save_le.text()
            if not os.path.exists(default_path):
                return
            os.startfile(os.path.dirname(default_path) if os.path.isfile(default_path) else default_path)
        elif self.sender() == self.current_model_btn:
            default_path = os.path.dirname(self.current_model_path.text()) if self.current_model_path.text() else os.path.expanduser("~")
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Model File", default_path, "GLB Files (*.glb);;All Files (*)")
            if file_path:
                self.current_model_path.setText(file_path)
                self.glb_viewer.load_model(file_path)
            
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
        self.path_to_image_le.setText(file_path)
        
    @asyncSlot()
    async def on_generate(self):
        if self.mode == "Trellis2":
            if not self.image_path:
                QMessageBox.warning(self, "Input Error", "Please drop an image file.")
                return
        
        if not self.path_to_save_le.text():
            QMessageBox.warning(self, "Input Error", "Please select a save path.")
            return
        
        self.generate_button.setEnabled(False)
        timeout = 300.0
        
        try:
            workflow = self.build_workflow()
            self.current_workflow_data = workflow
            
            async with httpx.AsyncClient(timeout=timeout) as session:
                prompt_id = await self.client.queue_prompt(session, workflow, timeout)
                
                if not prompt_id:
                    self.append_error_log("Failed to queue prompt.")
                    return

                self.my_current_prompt_id = prompt_id
                self.append_info_log(f"Started generation with prompt_id: {prompt_id}")
                
                await self.check_queue_position()

                start_time = time.time()
                while True:
                    if time.time() - start_time > timeout:
                        raise TimeoutError("Generation timed out.")
                    
                    history = await self.client.get_history(session, prompt_id)
                    if history:
                        break
                    
                    await asyncio.sleep(1)

                # 6. 결과 처리
                result = history
                outputs = result.get("outputs", {})
                # mesh_paths = await self.client.get_mesh_paths(outputs)
                
                if self.mode == "Trellis2":
                    save_path = self.path_to_save_le.text()
                    if not os.path.exists(save_path):
                        time.sleep(1)  # 잠시 대기 후 재시도
                    if not os.path.exists(save_path):
                        self.append_error_log("Save path does not exist.")
                        self.generate_button.setEnabled(True)
                        return
                    self.current_model_path.setText(save_path)
                    self.glb_viewer.load_model(save_path)
                    self.append_success_log(f"Mesh file Loaded: {os.path.basename(save_path)}")
                
                # if mesh_paths:
                #     source_path = mesh_paths[0]
                #     target_path = self.path_to_save_le.text()
                    
                #     # 폴더 생성 및 파일 복사
                #     os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                #     if os.path.exists(source_path):
                #         shutil.copy2(source_path, target_path)
                #         self.append_info_log(f"File saved to: {target_path}")
                        
                #         # 뷰어 로드
                #         self.current_model_path.setText(target_path)
                #         self.glb_viewer.load_model(target_path)
                #         self.append_info_log(f"Mesh file Loaded: {os.path.basename(target_path)}")
                #     else:
                #         self.append_error_log(f"Generated file not found at: {source_path}")
                else:
                    self.append_error_log("No mesh output found in history.")

        except httpx.ReadTimeout:
            self.append_error_log(f"Request timed out after {timeout}s.")
        except httpx.ConnectTimeout:
            self.append_error_log("Connection timed out. Check server.")
        except Exception as e:
            self.append_error_log(f"Error: {str(e)}")
            traceback.print_exc()
        finally:
            self.generate_button.setEnabled(True)
            self.my_current_prompt_id = None
            
            self.append_success_log("Generation process finished.")

    async def wait_for_my_job(self, client, prompt_id):
        """내 작업이 끝날 때까지 대기 (Polling History)"""
        while True:
            try:
                res = await client.get(f"{self.constants.COMFY_API_URL}/history/{prompt_id}")
                if res.status_code == 200 and prompt_id in res.json():
                    return
            except:
                pass
            await asyncio.sleep(1)

    def append_processing_log(self, message: str):
        if message != self.last_log_line:
            self.last_log_line = message
            previous_color = self.log_text.textColor()
            self.log_text.setTextColor(QColor(0, 250, 0))
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
            self.log_text.setTextColor(QColor(150, 150, 150))
            self.log_text.append(f"[Info] {message}")
            self.log_text.setTextColor(previous_color)
            
    def append_success_log(self, message: str):
        if message != self.last_log_line:
            self.last_log_line = message
            previous_color = self.log_text.textColor()
            self.log_text.setTextColor(QColor(0, 200, 255))
            self.log_text.append(f"[Success] {message}")
            self.log_text.setTextColor(previous_color)

    def build_workflow(self) -> dict:
        if self.mode == "Trellis2":
            workflow_name = "trellis2_img2mesh"
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")
        path = os.path.join(os.path.dirname(__file__), f"workflows/{workflow_name}.json")
        with open(path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        if self.mode == "Trellis2":
            image = self.image_path
            shutil.copy2(image, self.constants.COMFY_INPUT_DIR)
            workflow["9"]["inputs"]["image"] = os.path.basename(image)
            workflow["24"]["inputs"]["save_path"] = self.path_to_save_le.text()
            workflow["3"]["inputs"]["seed"] = randint(0, 2**31-1)
            workflow["5"]["inputs"]["seed"] = randint(0, 2**31-1)
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")
        return workflow
    
    def on_mode_change(self, mode: str):
        self.mode = mode
        if mode == "Trellis2":
            self.img2mesh_group.show()
            self.stack.setCurrentWidget(self.glb_viewer)
        else:
            QMessageBox.warning(self, "Mode Error", f"Unsupported mode selected: {mode}")
            
    def on_execution_start(self, prompt_id):
        if prompt_id == self.my_current_prompt_id:
            self.append_processing_log("My job started processing.")
        else:
            if self.my_current_prompt_id:
                asyncio.create_task(self.check_queue_position())

    def on_node_executing(self, node_id, prompt_id):
        if prompt_id == self.my_current_prompt_id:
            node_title = "Unknown Node"
            
            if self.current_workflow_data and node_id in self.current_workflow_data:
                node_data = self.current_workflow_data[node_id]
                node_title = node_data.get("_meta", {}).get("title") or node_data.get("class_type", f"Node {node_id}")

            self.append_processing_log(f"Executing: {node_title} (ID: {node_id})")

    def on_progress(self, value, max_val, msg):
        # if self.my_current_prompt_id:
        #     if self.progress_bar.maximum() == 0:
        #         self.progress_bar.setRange(0, 100)
            
        #     if max_val > 0:
        #         perc = int((value / max_val) * 100)
        #         self.progress_bar.setValue(perc)
        #         self.progress_bar.setFormat(f"Processing... {perc}%")
        pass

    def on_queue_update(self, queue_remaining):
        """전체 대기열 수 업데이트"""
        self.queue_label.setText(f"Queue Pending: {queue_remaining}")

    async def check_queue_position(self):
        """내 작업이 대기열의 몇 번째인지 확인"""
        if not self.my_current_prompt_id:
            return

        async with httpx.AsyncClient() as client:
            queue_info = await self.client.get_queue_info(client)
            if not queue_info: return

            pending = queue_info.get('queue_pending', [])
            running = queue_info.get('queue_running', [])
            
            for item in running:
                if item[1] == self.my_current_prompt_id:
                    return

            position = 0
            found = False
            for item in pending:
                position += 1
                if item[1] == self.my_current_prompt_id:
                    found = True
                    break
            
            if found:
                self.append_info_log(f"My job is queued at position {position}. Waiting for others to finish.")


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
