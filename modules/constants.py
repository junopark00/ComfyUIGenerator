import datetime

COMFY_INPUT_DIR = "/path/to/your/comfyui/input"
COMFY_OUTPUT_DIR = "/path/to/your/comfyui/output"
COMFY_API_URL = "http://localhost:8188"

FONT_DIR = "/source/font"

COMFY_TXT2IMG_SAMPLERS = [
    "euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp", "heun", "heunpp2","dpm_2", "dpm_2_ancestral",
    "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_2s_ancestral_cfg_pp", "dpmpp_sde", "dpmpp_sde_gpu",
    "dpmpp_2m", "dpmpp_2m_cfg_pp", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm", "lcm",
    "ipndm", "ipndm_v", "deis", "res_multistep", "res_multistep_cfg_pp", "res_multistep_ancestral", "res_multistep_ancestral_cfg_pp",
    "gradient_estimation", "gradient_estimation_cfg_pp", "er_sde", "seeds_2", "seeds_3", "ddim", "uni_pc", "uni_pc_bh2"
    ]
COMFY_TXT2IMG_SCHEDULERS = [
    "normal", "karras", "exponential", "sgm_uniform",
    "simple","ddm_uniform", "beta", "linear_quadratic","kl_optimal",
    ]

TXT2IMG_IMAGE_PREFIX = f"ImageGen/{datetime.datetime.now().strftime('%Y_%m_%d')}/image"
IMG2MESH_OBJ_PREFIX = f"MeshGen/{datetime.datetime.now().strftime('%Y_%m_%d')}/textured_mesh"
IMG2MESH_GLB_PREFIX = f"MeshGen/{datetime.datetime.now().strftime('%Y_%m_%d')}/mesh"