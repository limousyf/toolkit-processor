import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from ..core.config import settings
from ..core.models import ToolkitTemplate, CreateTemplateRequest, ToolDefinition, ArucoMarkerBounds


class TemplateService:
    """Service for managing toolkit templates."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or settings.toolkit_config_dir / "templates"
        self.images_dir = self.config_dir / "images"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _get_config_path(self, template_id: str) -> Path:
        return self.config_dir / f"{template_id}.json"

    def _get_image_path(self, template_id: str) -> Path:
        return self.images_dir / f"{template_id}.png"

    def list_templates(self) -> list[ToolkitTemplate]:
        """List all available templates."""
        templates = []
        for config_file in self.config_dir.glob("*.json"):
            try:
                template = self.get_template(config_file.stem)
                if template:
                    templates.append(template)
            except Exception:
                continue
        return sorted(templates, key=lambda t: t.name)

    def get_template(self, template_id: str) -> Optional[ToolkitTemplate]:
        """Get a specific template by ID."""
        config_path = self._get_config_path(template_id)
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            data = json.load(f)
            return ToolkitTemplate(**data)

    def create_template(self, request: CreateTemplateRequest) -> ToolkitTemplate:
        """Create a new template."""
        config_path = self._get_config_path(request.template_id)
        if config_path.exists():
            raise ValueError(f"Template '{request.template_id}' already exists")

        # Auto-assign slot_index if not set
        tools = []
        for i, tool in enumerate(request.tools):
            tool_data = tool.model_dump()
            tool_data["slot_index"] = i
            tools.append(ToolDefinition(**tool_data))

        now = datetime.utcnow()
        template = ToolkitTemplate(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            foam_color=request.foam_color,
            image_width=request.image_width,
            image_height=request.image_height,
            tools=tools,
            created_at=now,
            updated_at=now,
        )

        self._save_template(template)
        return template

    def update_template(self, template: ToolkitTemplate) -> ToolkitTemplate:
        """Update an existing template."""
        config_path = self._get_config_path(template.template_id)
        if not config_path.exists():
            raise ValueError(f"Template '{template.template_id}' not found")

        # Preserve aruco_bounds from existing template if not provided
        if template.aruco_bounds is None:
            existing = self.get_template(template.template_id)
            if existing and existing.aruco_bounds:
                template.aruco_bounds = existing.aruco_bounds

        # Ensure slot_index values are consistent
        tools = []
        for i, tool in enumerate(template.tools):
            tool_data = tool.model_dump()
            tool_data["slot_index"] = i
            tools.append(ToolDefinition(**tool_data))
        template.tools = tools

        template.updated_at = datetime.utcnow()
        self._save_template(template)
        return template

    def delete_template(self, template_id: str) -> bool:
        """Delete a template and its image."""
        config_path = self._get_config_path(template_id)
        if not config_path.exists():
            return False

        config_path.unlink()

        # Also delete the image if it exists
        image_path = self._get_image_path(template_id)
        if image_path.exists():
            image_path.unlink()

        return True

    def _save_template(self, template: ToolkitTemplate) -> Path:
        """Save template to disk."""
        config_path = self._get_config_path(template.template_id)
        with open(config_path, "w") as f:
            json.dump(template.model_dump(mode="json"), f, indent=2, default=str)
        return config_path

    def save_image(self, template_id: str, image_data: bytes) -> Path:
        """Save template reference image and detect ArUco markers."""
        image_path = self._get_image_path(template_id)
        with open(image_path, "wb") as f:
            f.write(image_data)

        # Try to detect ArUco markers and update template
        self._detect_and_save_aruco_bounds(template_id, image_path)

        return image_path

    def _detect_and_save_aruco_bounds(self, template_id: str, image_path: Path) -> None:
        """Detect ArUco markers in image and save bounds to template."""
        try:
            from ..cv.registration import ToolkitRegistration

            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                return

            # Detect markers
            registration = ToolkitRegistration(
                dictionary=settings.aruco_dictionary,
                marker_ids=settings.aruco_marker_ids,
            )
            markers = registration.detect_markers(image)

            # If all 4 markers found, save bounds
            if markers.all_found:
                bounds = ArucoMarkerBounds(
                    top_left=(markers.centers[0][0], markers.centers[0][1]),
                    top_right=(markers.centers[1][0], markers.centers[1][1]),
                    bottom_right=(markers.centers[2][0], markers.centers[2][1]),
                    bottom_left=(markers.centers[3][0], markers.centers[3][1]),
                )

                # Update template with bounds
                template = self.get_template(template_id)
                if template:
                    template.aruco_bounds = bounds
                    template.image_width = image.shape[1]
                    template.image_height = image.shape[0]
                    self._save_template(template)

        except Exception as e:
            # Don't fail image save if ArUco detection fails
            print(f"Warning: Could not detect ArUco markers: {e}")

    def save_image_base64(self, template_id: str, base64_data: str) -> Path:
        """Save template reference image from base64 string."""
        # Remove data URL prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        image_data = base64.b64decode(base64_data)
        return self.save_image(template_id, image_data)

    def get_image_path(self, template_id: str) -> Optional[Path]:
        """Get the path to the template's reference image if it exists."""
        image_path = self._get_image_path(template_id)
        return image_path if image_path.exists() else None

    def has_image(self, template_id: str) -> bool:
        """Check if a template has a reference image."""
        return self._get_image_path(template_id).exists()


# Singleton instance
template_service = TemplateService()
