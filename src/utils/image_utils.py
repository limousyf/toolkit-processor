import base64
from pathlib import Path
from typing import Union

import cv2
import numpy as np


def load_image(source: Union[str, Path, bytes]) -> np.ndarray:
    """Load an image from file path or bytes.

    Args:
        source: File path, Path object, or image bytes

    Returns:
        OpenCV image array (BGR format)

    Raises:
        ValueError: If image cannot be loaded
    """
    if isinstance(source, bytes):
        # Decode from bytes
        nparr = np.frombuffer(source, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        # Load from file path
        path = Path(source)
        if not path.exists():
            raise ValueError(f"Image file not found: {path}")
        image = cv2.imread(str(path))

    if image is None:
        raise ValueError(f"Failed to load image from: {source}")

    return image


def save_image(image: np.ndarray, path: Union[str, Path]) -> Path:
    """Save an image to file.

    Args:
        image: OpenCV image array
        path: Output file path

    Returns:
        Path to saved file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return path


def encode_image_base64(image: np.ndarray, format: str = ".png") -> str:
    """Encode an OpenCV image to base64 string.

    Args:
        image: OpenCV image array
        format: Image format (e.g., '.png', '.jpg')

    Returns:
        Base64 encoded string with data URI prefix
    """
    success, buffer = cv2.imencode(format, image)
    if not success:
        raise ValueError(f"Failed to encode image to {format}")

    b64_string = base64.b64encode(buffer).decode("utf-8")
    mime_type = "image/png" if format == ".png" else "image/jpeg"
    return f"data:{mime_type};base64,{b64_string}"


def decode_image_base64(b64_string: str) -> np.ndarray:
    """Decode a base64 string to OpenCV image.

    Args:
        b64_string: Base64 encoded image (with or without data URI prefix)

    Returns:
        OpenCV image array
    """
    # Remove data URI prefix if present
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]

    img_bytes = base64.b64decode(b64_string)
    return load_image(img_bytes)


def resize_image(image: np.ndarray, max_dimension: int = 1920) -> np.ndarray:
    """Resize image if it exceeds max dimension while preserving aspect ratio.

    Args:
        image: OpenCV image array
        max_dimension: Maximum width or height

    Returns:
        Resized image (or original if already within bounds)
    """
    height, width = image.shape[:2]

    if max(height, width) <= max_dimension:
        return image

    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def create_thumbnail(image_base64: str, max_width: int = 150) -> str:
    """Create a thumbnail from a base64 encoded image.

    Args:
        image_base64: Base64 data URL of the image
        max_width: Maximum width of thumbnail (height scales proportionally)

    Returns:
        Base64 data URL of the thumbnail
    """
    image = decode_image_base64(image_base64)
    height, width = image.shape[:2]

    if width > max_width:
        scale = max_width / width
        new_height = int(height * scale)
        image = cv2.resize(image, (max_width, new_height), interpolation=cv2.INTER_AREA)

    return encode_image_base64(image, ".jpg")
