"""Tests for playbook loader."""

import tempfile
from pathlib import Path

import pytest

from patchweave.core.loader import PlaybookLoader, PlaybookLoadError
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType


@pytest.fixture
def temp_playbooks_dir(tmp_path: Path) -> Path:
    """Create a temporary playbooks directory."""
    return tmp_path / "playbooks"


@pytest.fixture
def valid_playbook_yaml() -> str:
    """Valid playbook YAML content."""
    return """
id: "test-playbook-123"
name: "Test S3 Encryption Playbook"
description: "Enable encryption for S3 buckets"
vulnerability_type: s3_encryption_disabled
cloud_provider: AWS
resource_type: "AWS::S3::Bucket"
severity: High
version: "1.0.0"

search_text: |
  S3 bucket encryption server-side AES-256 SSE

tags:
  - s3
  - encryption

compliance_frameworks:
  - "CIS AWS 2.1.1"

required_permissions:
  - s3:GetBucketEncryption
  - s3:PutBucketEncryption

estimated_execution_time_seconds: 15

pre_check_code: |
  def pre_check(bucket_name: str, **kwargs) -> dict:
      return {"needs_remediation": True, "bucket": "{{BUCKET_NAME}}"}

remediation_code: |
  def remediate(bucket_name: str, **kwargs) -> dict:
      return {"success": True, "bucket": "{{BUCKET_NAME}}"}

post_check_code: |
  def post_check(bucket_name: str, **kwargs) -> dict:
      return {"verified": True, "bucket": "{{BUCKET_NAME}}"}
"""


@pytest.fixture
def minimal_playbook_yaml() -> str:
    """Minimal valid playbook YAML."""
    return """
name: "Minimal Playbook"
description: "A minimal playbook"
vulnerability_type: unknown
remediation_code: "pass"
pre_check_code: "pass"
post_check_code: "pass"
"""


class TestPlaybookLoader:
    """Tests for PlaybookLoader class."""

    def test_initialization_default_dir(self) -> None:
        """Test loader initialization with default directory."""
        loader = PlaybookLoader()
        assert loader.playbooks_dir is not None

    def test_initialization_custom_dir(self, temp_playbooks_dir: Path) -> None:
        """Test loader initialization with custom directory."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        assert loader.playbooks_dir == temp_playbooks_dir

    def test_load_file_valid(
        self, temp_playbooks_dir: Path, valid_playbook_yaml: str
    ) -> None:
        """Test loading a valid playbook file."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "test_playbook.yaml"
        file_path.write_text(valid_playbook_yaml)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbook = loader.load_file(file_path)

        assert playbook.id == "test-playbook-123"
        assert playbook.name == "Test S3 Encryption Playbook"
        assert playbook.vulnerability_type == VulnerabilityType.S3_ENCRYPTION_DISABLED
        assert playbook.cloud_provider == CloudProvider.AWS
        assert playbook.severity == Severity.HIGH
        assert "s3" in playbook.tags
        assert "encryption" in playbook.tags
        assert "s3:GetBucketEncryption" in playbook.required_permissions

    def test_load_file_generates_id(
        self, temp_playbooks_dir: Path, minimal_playbook_yaml: str
    ) -> None:
        """Test that ID is generated if not provided."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "minimal.yaml"
        file_path.write_text(minimal_playbook_yaml)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbook = loader.load_file(file_path)

        assert playbook.id is not None
        assert len(playbook.id) > 0

    def test_load_file_not_found(self, temp_playbooks_dir: Path) -> None:
        """Test loading a non-existent file."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        with pytest.raises(PlaybookLoadError, match="not found"):
            loader.load_file(temp_playbooks_dir / "nonexistent.yaml")

    def test_load_file_invalid_yaml(self, temp_playbooks_dir: Path) -> None:
        """Test loading a file with invalid YAML."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "invalid.yaml"
        file_path.write_text("this: is: not: valid: yaml:")

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        with pytest.raises(PlaybookLoadError, match="Invalid YAML"):
            loader.load_file(file_path)

    def test_load_file_not_mapping(self, temp_playbooks_dir: Path) -> None:
        """Test loading a YAML file that's not a mapping."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "list.yaml"
        file_path.write_text("- item1\n- item2")

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        with pytest.raises(PlaybookLoadError, match="YAML mapping"):
            loader.load_file(file_path)

    def test_load_all_empty_directory(self, temp_playbooks_dir: Path) -> None:
        """Test loading from empty directory."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbooks = loader.load_all()

        assert playbooks == []

    def test_load_all_nonexistent_directory(self) -> None:
        """Test loading from non-existent directory."""
        loader = PlaybookLoader(playbooks_dir="/nonexistent/path")
        playbooks = loader.load_all()

        assert playbooks == []

    def test_load_all_multiple_files(
        self, temp_playbooks_dir: Path, valid_playbook_yaml: str
    ) -> None:
        """Test loading multiple playbook files."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        # Create multiple playbook files
        for i in range(3):
            yaml_content = valid_playbook_yaml.replace(
                'id: "test-playbook-123"', f'id: "test-playbook-{i}"'
            ).replace(
                'name: "Test S3 Encryption Playbook"',
                f'name: "Test Playbook {i}"',
            )
            file_path = temp_playbooks_dir / f"playbook_{i}.yaml"
            file_path.write_text(yaml_content)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbooks = loader.load_all()

        assert len(playbooks) == 3

    def test_load_all_handles_errors(
        self, temp_playbooks_dir: Path, valid_playbook_yaml: str
    ) -> None:
        """Test that load_all continues on errors."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        # Create a valid file
        valid_file = temp_playbooks_dir / "valid.yaml"
        valid_file.write_text(valid_playbook_yaml)

        # Create an invalid file
        invalid_file = temp_playbooks_dir / "invalid.yaml"
        invalid_file.write_text("not: valid: yaml:")

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbooks = loader.load_all()

        # Should have loaded the valid one
        assert len(playbooks) == 1

    def test_load_all_yaml_and_yml(self, temp_playbooks_dir: Path) -> None:
        """Test loading both .yaml and .yml files."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        yaml_content = """
name: "Test Playbook"
description: "Test"
vulnerability_type: unknown
remediation_code: "pass"
pre_check_code: "pass"
post_check_code: "pass"
"""

        (temp_playbooks_dir / "test1.yaml").write_text(yaml_content)
        (temp_playbooks_dir / "test2.yml").write_text(yaml_content)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbooks = loader.load_all()

        assert len(playbooks) == 2


class TestPlaybookLoaderValidation:
    """Tests for playbook validation."""

    def test_validate_complete_playbook(
        self, temp_playbooks_dir: Path, valid_playbook_yaml: str
    ) -> None:
        """Test validation passes for complete playbook."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "valid.yaml"
        file_path.write_text(valid_playbook_yaml)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbook = loader.load_file(file_path)
        errors = loader.validate_playbook(playbook)

        assert len(errors) == 0

    def test_validate_missing_fields(
        self, temp_playbooks_dir: Path, minimal_playbook_yaml: str
    ) -> None:
        """Test validation catches missing fields."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_playbooks_dir / "minimal.yaml"
        file_path.write_text(minimal_playbook_yaml)

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)
        playbook = loader.load_file(file_path)
        errors = loader.validate_playbook(playbook)

        # Should have errors for unknown vuln type and missing tokens
        assert len(errors) > 0
        assert any("vulnerability_type" in e for e in errors)

    def test_validate_unknown_vulnerability_type(self) -> None:
        """Test validation catches unknown vulnerability type."""
        from patchweave.models.playbook import Playbook
        from patchweave.models.enums import VulnerabilityType

        loader = PlaybookLoader()
        playbook = Playbook(
            id="test",
            name="Test",
            description="Test",
            vulnerability_type=VulnerabilityType.UNKNOWN,
            cloud_provider=CloudProvider.AWS,
            resource_type="Test",
            severity=Severity.MEDIUM,
            search_text="test",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        )

        errors = loader.validate_playbook(playbook)
        assert any("vulnerability_type" in e for e in errors)

    def test_validate_no_token_placeholders(self) -> None:
        """Test validation warns about missing token placeholders."""
        from patchweave.models.playbook import Playbook

        loader = PlaybookLoader()
        playbook = Playbook(
            id="test",
            name="Test",
            description="Test",
            vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
            cloud_provider=CloudProvider.AWS,
            resource_type="Test",
            severity=Severity.MEDIUM,
            search_text="test",
            remediation_code="pass",  # No tokens
            pre_check_code="pass",
            post_check_code="pass",
        )

        errors = loader.validate_playbook(playbook)
        assert any("TOKEN" in e for e in errors)


class TestPlaybookLoaderParsing:
    """Tests for playbook field parsing."""

    def test_parse_vulnerability_types(self, temp_playbooks_dir: Path) -> None:
        """Test parsing various vulnerability types."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        vuln_types = [
            ("s3_public_access", VulnerabilityType.S3_PUBLIC_ACCESS),
            ("s3_encryption_disabled", VulnerabilityType.S3_ENCRYPTION_DISABLED),
            ("security_group_open_ssh", VulnerabilityType.SECURITY_GROUP_OPEN_SSH),
            ("rds_publicly_accessible", VulnerabilityType.RDS_PUBLICLY_ACCESSIBLE),
            ("ebs_unencrypted", VulnerabilityType.EBS_UNENCRYPTED),
            ("iam_mfa_disabled", VulnerabilityType.IAM_MFA_DISABLED),
        ]

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        for yaml_val, expected_type in vuln_types:
            yaml_content = f"""
name: "Test"
description: "Test"
vulnerability_type: {yaml_val}
remediation_code: "pass"
pre_check_code: "pass"
post_check_code: "pass"
"""
            file_path = temp_playbooks_dir / f"test_{yaml_val}.yaml"
            file_path.write_text(yaml_content)

            playbook = loader.load_file(file_path)
            assert playbook.vulnerability_type == expected_type

    def test_parse_severities(self, temp_playbooks_dir: Path) -> None:
        """Test parsing various severity levels."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        severities = [
            ("Critical", Severity.CRITICAL),
            ("High", Severity.HIGH),
            ("Medium", Severity.MEDIUM),
            ("Low", Severity.LOW),
            ("Info", Severity.INFO),
        ]

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        for yaml_val, expected_sev in severities:
            yaml_content = f"""
name: "Test"
description: "Test"
vulnerability_type: unknown
severity: {yaml_val}
remediation_code: "pass"
pre_check_code: "pass"
post_check_code: "pass"
"""
            file_path = temp_playbooks_dir / f"test_{yaml_val}.yaml"
            file_path.write_text(yaml_content)

            playbook = loader.load_file(file_path)
            assert playbook.severity == expected_sev

    def test_parse_cloud_providers(self, temp_playbooks_dir: Path) -> None:
        """Test parsing cloud providers."""
        temp_playbooks_dir.mkdir(parents=True, exist_ok=True)

        # Currently only AWS is supported
        providers = [
            ("AWS", CloudProvider.AWS),
        ]

        loader = PlaybookLoader(playbooks_dir=temp_playbooks_dir)

        for yaml_val, expected_prov in providers:
            yaml_content = f"""
name: "Test"
description: "Test"
vulnerability_type: unknown
cloud_provider: {yaml_val}
remediation_code: "pass"
pre_check_code: "pass"
post_check_code: "pass"
"""
            file_path = temp_playbooks_dir / f"test_{yaml_val}.yaml"
            file_path.write_text(yaml_content)

            playbook = loader.load_file(file_path)
            assert playbook.cloud_provider == expected_prov
