from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    toolkit_config_dir: Path = base_dir / "config" / "toolkits"
    reference_image_dir: Path = base_dir / "img" / "reference"
    upload_dir: Path = base_dir / "img" / "uploads"

    # Detection parameters (for dark foam)
    brightness_threshold: int = 60  # Pixels above this are "bright" (0-255)
    occupied_ratio_threshold: float = 0.25  # 25% bright pixels = occupied
    saturation_threshold: int = 40  # For detecting colored tools
    color_ratio_threshold: float = 0.15  # 15% colored pixels contributes to detection

    # Edge detection (for metallic reflections)
    edge_density_threshold: float = 0.05  # Edge pixel ratio

    # Confidence calculation weights
    weight_brightness: float = 0.5
    weight_saturation: float = 0.3
    weight_edges: float = 0.2

    # ArUco Registration (Global Standard)
    aruco_enabled: bool = True
    aruco_dictionary: str = "DICT_4X4_50"
    aruco_marker_ids: list[int] = [0, 1, 2, 3]  # TL, TR, BR, BL
    aruco_canonical_width: int = 1000
    aruco_canonical_height: int = 800
    aruco_min_markers: int = 3  # Minimum markers for homography
    aruco_debug: bool = False

    # API settings
    api_title: str = "Toolkit Processor API"
    api_version: str = "1.0.0"
    debug: bool = True

    class Config:
        env_prefix = "TOOLKIT_"


settings = Settings()

# Ensure directories exist
settings.toolkit_config_dir.mkdir(parents=True, exist_ok=True)
settings.reference_image_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
