import json
from pathlib import Path
from typing import Optional

from ..core.config import settings
from ..core.models import ToolkitConfig, CreateToolkitRequest


class ToolkitService:
    """Service for managing toolkit configurations."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the service.

        Args:
            config_dir: Directory containing toolkit JSON files
        """
        self.config_dir = config_dir or settings.toolkit_config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_config_path(self, toolkit_id: str) -> Path:
        """Get the file path for a toolkit config."""
        return self.config_dir / f"{toolkit_id}.json"

    def list_toolkits(self) -> list[ToolkitConfig]:
        """List all available toolkit configurations.

        Returns:
            List of ToolkitConfig objects
        """
        toolkits = []
        for config_file in self.config_dir.glob("*.json"):
            try:
                toolkit = self.get_toolkit(config_file.stem)
                if toolkit:
                    toolkits.append(toolkit)
            except Exception:
                # Skip invalid config files
                continue
        return toolkits

    def get_toolkit(self, toolkit_id: str) -> Optional[ToolkitConfig]:
        """Get a specific toolkit configuration.

        Args:
            toolkit_id: Unique identifier of the toolkit

        Returns:
            ToolkitConfig or None if not found
        """
        config_path = self._get_config_path(toolkit_id)
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            data = json.load(f)
            return ToolkitConfig(**data)

    def create_toolkit(self, request: CreateToolkitRequest) -> ToolkitConfig:
        """Create a new toolkit configuration.

        Args:
            request: CreateToolkitRequest with toolkit data

        Returns:
            Created ToolkitConfig

        Raises:
            ValueError: If toolkit already exists
        """
        config_path = self._get_config_path(request.toolkit_id)
        if config_path.exists():
            raise ValueError(f"Toolkit '{request.toolkit_id}' already exists")

        toolkit = ToolkitConfig(
            toolkit_id=request.toolkit_id,
            name=request.name,
            description=request.description,
            foam_color=request.foam_color,
            dimensions=request.dimensions,
            tools=request.tools,
        )

        self.save_toolkit(toolkit)
        return toolkit

    def save_toolkit(self, toolkit: ToolkitConfig) -> Path:
        """Save a toolkit configuration to disk.

        Args:
            toolkit: ToolkitConfig to save

        Returns:
            Path to saved config file
        """
        config_path = self._get_config_path(toolkit.toolkit_id)

        with open(config_path, "w") as f:
            json.dump(toolkit.model_dump(mode="json"), f, indent=2)

        return config_path

    def update_toolkit(self, toolkit: ToolkitConfig) -> ToolkitConfig:
        """Update an existing toolkit configuration.

        Args:
            toolkit: ToolkitConfig with updated data

        Returns:
            Updated ToolkitConfig

        Raises:
            ValueError: If toolkit does not exist
        """
        config_path = self._get_config_path(toolkit.toolkit_id)
        if not config_path.exists():
            raise ValueError(f"Toolkit '{toolkit.toolkit_id}' not found")

        self.save_toolkit(toolkit)
        return toolkit

    def delete_toolkit(self, toolkit_id: str) -> bool:
        """Delete a toolkit configuration.

        Args:
            toolkit_id: ID of toolkit to delete

        Returns:
            True if deleted, False if not found
        """
        config_path = self._get_config_path(toolkit_id)
        if not config_path.exists():
            return False

        config_path.unlink()
        return True


# Singleton instance
toolkit_service = ToolkitService()
