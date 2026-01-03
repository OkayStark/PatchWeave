"""
Playbook loader for PatchWeave.

Loads playbook definitions from YAML files and converts them
to Playbook models for storage in ChromaDB.
"""

import uuid
from pathlib import Path
from typing import Any

import yaml

from patchweave.config import settings
from patchweave.logging import get_logger
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
from patchweave.models.playbook import Playbook

log = get_logger(__name__)


class PlaybookLoadError(Exception):
    """Error loading a playbook file."""
    pass


class PlaybookLoader:
    """
    Loads playbook definitions from YAML files.
    
    Playbook YAML format:
    ```yaml
    id: optional-uuid (generated if not provided)
    name: "Human readable name"
    description: "What this playbook does"
    vulnerability_type: s3_public_access
    cloud_provider: AWS
    resource_type: "AWS::S3::Bucket"
    severity: Critical
    search_text: "Keywords for semantic search"
    
    remediation_code: |
      # Python/Boto3 code
      
    pre_check_code: |
      # Verification code
      
    post_check_code: |
      # Post-fix verification
      
    required_permissions:
      - s3:GetBucketPolicy
      - s3:PutBucketPolicy
      
    tags:
      - s3
      - public-access
      
    compliance_frameworks:
      - CIS AWS 2.1.1
    ```
    """

    def __init__(self, playbooks_dir: str | Path | None = None):
        """
        Initialize the loader.
        
        Args:
            playbooks_dir: Directory containing playbook YAML files
        """
        self.playbooks_dir = Path(playbooks_dir or settings.playbooks_directory)
        log.info("playbook_loader_initialized", directory=str(self.playbooks_dir))

    def load_file(self, file_path: Path | str) -> Playbook:
        """
        Load a single playbook from a YAML file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Playbook model
            
        Raises:
            PlaybookLoadError: If the file cannot be loaded or parsed
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise PlaybookLoadError(f"Playbook file not found: {file_path}")
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PlaybookLoadError(f"Invalid YAML in {file_path}: {e}") from e
            
        if not isinstance(data, dict):
            raise PlaybookLoadError(f"Playbook file must contain a YAML mapping: {file_path}")

        try:
            playbook = self._dict_to_playbook(data, source_file=str(file_path))
            log.info(
                "playbook_loaded",
                file=str(file_path),
                playbook_id=playbook.id,
                name=playbook.name,
            )
            return playbook
        except Exception as e:
            raise PlaybookLoadError(f"Failed to parse playbook {file_path}: {e}") from e

    def _dict_to_playbook(self, data: dict[str, Any], source_file: str = "") -> Playbook:
        """
        Convert a dictionary to a Playbook model.
        
        Args:
            data: Dictionary from YAML
            source_file: Source file path for error messages
            
        Returns:
            Playbook model
        """
        # Generate ID if not provided
        playbook_id = data.get("id") or str(uuid.uuid4())
        
        # Parse vulnerability type
        vuln_type_str = data.get("vulnerability_type", "unknown")
        try:
            vulnerability_type = VulnerabilityType(vuln_type_str.lower())
        except ValueError:
            log.warning(
                "unknown_vulnerability_type",
                type=vuln_type_str,
                file=source_file,
            )
            vulnerability_type = VulnerabilityType.UNKNOWN
            
        # Parse cloud provider
        provider_str = data.get("cloud_provider", "AWS").upper()
        try:
            cloud_provider = CloudProvider(provider_str)
        except ValueError:
            cloud_provider = CloudProvider.AWS
            
        # Parse severity
        severity_str = data.get("severity", "Medium")
        try:
            severity = Severity(severity_str.capitalize())
        except ValueError:
            severity = Severity.MEDIUM

        return Playbook(
            id=playbook_id,
            name=data.get("name", "Unnamed Playbook"),
            description=data.get("description", ""),
            vulnerability_type=vulnerability_type,
            cloud_provider=cloud_provider,
            resource_type=data.get("resource_type", "Unknown"),
            severity=severity,
            search_text=data.get("search_text", data.get("name", "")),
            remediation_code=data.get("remediation_code", ""),
            pre_check_code=data.get("pre_check_code", ""),
            post_check_code=data.get("post_check_code", ""),
            required_permissions=data.get("required_permissions", []),
            estimated_execution_time_seconds=data.get("estimated_execution_time_seconds", 30),
            tags=data.get("tags", []),
            compliance_frameworks=data.get("compliance_frameworks", []),
            version=data.get("version", "1.0.0"),
            created_by=data.get("created_by", "PatchWeave"),
        )

    def load_all(self) -> list[Playbook]:
        """
        Load all playbooks from the playbooks directory.
        
        Returns:
            List of loaded Playbook models
        """
        if not self.playbooks_dir.exists():
            log.warning("playbooks_directory_not_found", directory=str(self.playbooks_dir))
            return []
            
        playbooks: list[Playbook] = []
        errors: list[str] = []
        
        for file_path in self.playbooks_dir.glob("*.yaml"):
            try:
                playbook = self.load_file(file_path)
                playbooks.append(playbook)
            except PlaybookLoadError as e:
                errors.append(str(e))
                log.error("playbook_load_failed", file=str(file_path), error=str(e))
                
        # Also check .yml extension
        for file_path in self.playbooks_dir.glob("*.yml"):
            try:
                playbook = self.load_file(file_path)
                playbooks.append(playbook)
            except PlaybookLoadError as e:
                errors.append(str(e))
                log.error("playbook_load_failed", file=str(file_path), error=str(e))

        log.info(
            "playbooks_loaded",
            total=len(playbooks),
            errors=len(errors),
            directory=str(self.playbooks_dir),
        )
        
        return playbooks

    def validate_playbook(self, playbook: Playbook) -> list[str]:
        """
        Validate a playbook for completeness.
        
        Args:
            playbook: Playbook to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []
        
        if not playbook.name:
            errors.append("Playbook name is required")
            
        if not playbook.description:
            errors.append("Playbook description is required")
            
        if playbook.vulnerability_type == VulnerabilityType.UNKNOWN:
            errors.append("Valid vulnerability_type is required")
            
        if not playbook.remediation_code:
            errors.append("remediation_code is required")
            
        if not playbook.pre_check_code:
            errors.append("pre_check_code is required")
            
        if not playbook.post_check_code:
            errors.append("post_check_code is required")
            
        if not playbook.search_text:
            errors.append("search_text is required for matching")
            
        # Check for token placeholders in code
        code_fields = [
            playbook.remediation_code,
            playbook.pre_check_code,
            playbook.post_check_code,
        ]
        has_tokens = any("{{" in code for code in code_fields)
        if not has_tokens:
            errors.append("Code should contain {{TOKEN}} placeholders for parameterization")

        return errors


# Global instance
_playbook_loader: PlaybookLoader | None = None


def get_playbook_loader() -> PlaybookLoader:
    """Get or create the global playbook loader instance."""
    global _playbook_loader
    if _playbook_loader is None:
        _playbook_loader = PlaybookLoader()
    return _playbook_loader


def load_and_index_playbooks() -> int:
    """
    Load all playbooks and add them to ChromaDB.
    
    Convenience function for initialization.
    
    Returns:
        Number of playbooks indexed
    """
    from patchweave.core.chromadb import get_playbook_store
    
    loader = get_playbook_loader()
    store = get_playbook_store()
    
    playbooks = loader.load_all()
    
    if playbooks:
        store.add_playbooks(playbooks)
        
    log.info("playbooks_indexed", count=len(playbooks))
    return len(playbooks)
