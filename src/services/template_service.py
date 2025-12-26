import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.config import settings
from ..core.models import ToolkitTemplate, CreateTemplateRequest, ToolDefinition


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
        """Save template reference image."""
        image_path = self._get_image_path(template_id)
        with open(image_path, "wb") as f:
            f.write(image_data)
        return image_path

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
