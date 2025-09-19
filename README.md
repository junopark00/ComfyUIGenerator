# ComfyUI API Client
![main](/source/img2mesh_result.png)
A modern PySide6-based GUI application for interacting with ComfyUI API, supporting both text-to-image generation and image-to-mesh conversion with an integrated 3D viewer.

## Features

### 🎨 Text to Image Generation
- Generate high-quality images from text prompts
- Configurable sampling methods, schedulers, and generation parameters
- Real-time generation progress monitoring
- Automatic duplicate file handling with OS-appropriate naming conventions

### 🎯 Image to Mesh Conversion
- Convert 2D images into 3D meshes (.obj and .glb formats)
- Interactive 3D mesh viewer with Three.js integration
- Support for Delight algorithm for enhanced texture quality
- Configurable mesh parameters (face count, guidance scale, steps)

### 🖥️ User Interface
- Modern dark theme with custom Lato font integration
- Drag-and-drop image input with preview
- Real-time log monitoring with color-coded messages
- Responsive layout with integrated 3D viewer
- Cross-platform compatible (Windows, macOS, Linux)

## Requirements

### Python Dependencies
```
PySide6
qasync
qdarktheme
httpx
Pillow (PIL)
```

### External Dependencies
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) server running with API enabled
- Three.js libraries (automatically managed by the application)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/comfyui-api-client.git
   cd comfyui-api-client
   ```

2. **Install Python dependencies**
   ```bash
   pip install PySide6 qasync qdarktheme httpx Pillow
   ```

3. **Configure ComfyUI connection**
   
   Edit `modules/constants.py` to match your ComfyUI setup:
   ```python
   COMFY_INPUT_DIR = "/path/to/comfyui/input"
   COMFY_OUTPUT_DIR = "/path/to/comfyui/output" 
   COMFY_API_URL = "http://localhost:8188"  # Your ComfyUI API URL
   ```

4. **Run the application**
   ```bash
   python main_window.py
   ```

## Configuration

### ComfyUI Server Setup
1. Ensure ComfyUI is running with API enabled
2. The default API endpoint is `http://localhost:8188`
3. Make sure the input/output directories are accessible

### Workflow Files
The application uses JSON workflow files located in the `workflows/` directory:
- `text2image.json` - Text-to-image generation workflow
- `image2mesh.json` - Image-to-mesh conversion workflow
- `image2mesh_delight.json` - Enhanced mesh generation with Delight algorithm

## Usage

### Text to Image Generation
1. Select "text2image" from the mode dropdown
2. Enter your text prompt in the text area
3. Adjust generation parameters (sampler, guidance, steps, etc.)
4. Choose output directory
5. Click "Generate"

### Image to Mesh Conversion
1. Select "image2mesh" from the mode dropdown  
2. Drag and drop an image file into the designated area
3. Configure mesh parameters:
   - **Guidance Scale**: Controls adherence to input image
   - **Steps**: Number of diffusion steps
   - **Max Face Num**: Maximum number of mesh faces
   - **Apply Delight**: Enhanced texture quality option
4. Choose output directory
5. Click "Generate"

### 3D Mesh Viewer
- Automatically opens generated .glb files
- Interactive controls:
  - Mouse drag: Rotate camera
  - Mouse wheel: Zoom in/out
  - Right-click drag: Pan camera
- Grid and wireframe view options
- Lighting controls

## Project Structure

```
comfyui-api-client/
├── main_window.py              # Main application entry point
├── modules/
│   ├── constants.py            # Configuration constants
│   ├── dragdrop_label.py       # Drag-and-drop image widget
│   ├── threejs_viewer.py       # 3D mesh viewer component
│   ├── alternative_viewer.py   # Alternative viewer implementation
│   └── ThreeJS/               # Three.js libraries and resources
├── workflows/                  # ComfyUI workflow JSON files
├── source/
│   ├── font/                  # Lato font files
│   └── icon/                  # Application icons
└── README.md
```

## API Integration

The application communicates with ComfyUI through its REST API:
- **Queue Prompt**: `/prompt` - Submit generation requests
- **Check Queue**: `/queue` - Monitor generation status  
- **Get History**: `/history/{prompt_id}` - Retrieve results
- **Download Files**: `/view` - Download generated content

## Customization

### Adding New Workflows
1. Create a new JSON workflow file in the `workflows/` directory
2. Update the mode dropdown in `main_window.py`
3. Add workflow-specific parameter handling in `build_workflow()`

### Modifying UI Themes
The application uses `qdarktheme` with custom styling in `main_window.py`. Modify the `setStyleSheet()` calls to customize appearance.

### Extending 3D Viewer
The Three.js viewer (`modules/threejs_viewer.py`) can be extended with additional features:
- New file format support
- Additional rendering modes
- Post-processing effects
- Animation controls

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The underlying AI generation framework
- [Three.js](https://threejs.org/) - 3D graphics library for mesh visualization
- [PySide6](https://doc.qt.io/qtforpython/) - Python UI framework
- [Lato Font](https://fonts.google.com/specimen/Lato) - Typography


**Note**: This application requires a running ComfyUI server with appropriate models installed. Please refer to the [ComfyUI documentation](https://github.com/comfyanonymous/ComfyUI) for server setup instructions.