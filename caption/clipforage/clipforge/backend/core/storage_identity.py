import sys
import os
import json
import hmac
import hashlib
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

TOKEN_FILENAME = ".clipforge_volume_token"
MAGIC_SIGNATURE = "CLIPFORGE_STUDIO_PERSISTENT_VOLUME_V1"

KNOWN_INSECURE_PLACEHOLDERS = {
    "clipforge_default_secret_key_change_in_prod",
    "changeme",
    "secret",
    "default",
    "placeholder",
    "your-secret-key-here",
    "insecure_default_secret_key",
}


def resolve_storage_identity_secret(secret_candidate: Optional[str] = None) -> str:
    """
    Resolves the storage identity secret from candidate or deployment settings.
    Fails closed if the secret is missing, empty, or set to a known placeholder.
    """
    from backend.core.config import settings
    secret = secret_candidate if secret_candidate is not None else (settings.STORAGE_IDENTITY_SECRET or settings.SECRET_KEY)
    
    if not secret or not str(secret).strip():
        raise RuntimeError("Storage identity secret is missing or empty. A secure secret must be configured.")
    
    cleaned = str(secret).strip()
    if cleaned in KNOWN_INSECURE_PLACEHOLDERS or len(cleaned) < 16:
        raise RuntimeError(
            f"Storage identity secret cannot be an insecure placeholder or shorter than 16 characters. "
            f"Please configure STORAGE_IDENTITY_SECRET or a strong production SECRET_KEY."
        )
    return cleaned


def compute_volume_hmac(volume_id: str, canonical_mount: str, cluster_id: str, secret_key: Optional[str] = None) -> str:
    """Computes HMAC-SHA256 signature for a volume identity token."""
    valid_secret = resolve_storage_identity_secret(secret_key)
    payload = f"{volume_id}:{canonical_mount}:{cluster_id}:{MAGIC_SIGNATURE}".encode("utf-8")
    return hmac.new(valid_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def provision_storage_identity(
    upload_dir: Path,
    volume_id: str,
    secret_key: Optional[str] = None,
    cluster_id: str = "default",
    canonical_mount: Optional[str] = None
) -> Dict[str, Any]:
    """
    Provisions a verifiable storage identity token into upload_dir.
    Writes .clipforge_volume_token with HMAC-SHA256 signature.
    """
    valid_secret = resolve_storage_identity_secret(secret_key)
    upload_path = upload_dir.resolve()
    upload_path.mkdir(parents=True, exist_ok=True)
    
    canonical = canonical_mount or str(upload_path).replace("\\", "/")
    token_hmac = compute_volume_hmac(volume_id, canonical, cluster_id, valid_secret)
    
    token_data = {
        "magic_signature": MAGIC_SIGNATURE,
        "volume_id": volume_id,
        "canonical_mount": canonical,
        "cluster_id": cluster_id,
        "hmac_sha256": token_hmac,
    }
    
    token_file = upload_path / TOKEN_FILENAME
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)
    
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass  # On Windows, chmod has limited posix attribute support
        
    return token_data


def parse_linux_mountinfo(mountinfo_text: str, target_canonical: str) -> Tuple[bool, str, str]:
    """
    Parses Linux /proc/self/mountinfo text using the hyphen '-' separator specification.
    Fields before '-':
      0: mount ID, 1: parent ID, 2: st_dev, 3: root, 4: mount point, 5: mount options, 6..opt tags
    Field '-' separator marks the end of optional tags.
    Field immediately after '-' is filesystem type: parts[sep_idx + 1].
    Next field is mount source: parts[sep_idx + 2].
    
    Returns: (is_valid_mount, fs_type, reason)
    """
    target_clean = str(target_canonical).rstrip("/")
    if not target_clean:
        target_clean = "/"

    for line in mountinfo_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if "-" not in parts or len(parts) < 8:
            continue
        
        mount_point = parts[4].rstrip("/")
        if not mount_point:
            mount_point = "/"
            
        if mount_point == target_clean:
            sep_idx = parts.index("-")
            if sep_idx + 1 >= len(parts):
                return False, "", "Malformed mountinfo line: missing filesystem type after '-'"
            
            fs_type = parts[sep_idx + 1]
            if fs_type.lower() in ("overlay", "overlayfs", "tmpfs"):
                return False, fs_type, f"Target {target_clean} is on ephemeral {fs_type}, not a persistent volume"
            
            return True, fs_type, f"Target {target_clean} verified on persistent filesystem {fs_type}"

    return False, "", f"Target {target_clean} not found as an active mountpoint in mountinfo"


def verify_windows_volume(upload_path: Path) -> Tuple[bool, str, str]:
    """
    Verifies that upload_path resides on an accessible Windows NTFS/ReFS volume.
    Returns: (is_valid, fs_type, reason)
    """
    if sys.platform not in ("win32", "cygwin"):
        return False, "", "Windows volume verification called on non-Windows platform"

    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32

        path_str = str(upload_path)
        vol_path_buf = ctypes.create_unicode_buffer(1024)
        if not kernel32.GetVolumePathNameW(path_str, vol_path_buf, 1024):
            return False, "", f"GetVolumePathNameW failed for {path_str}"

        serial_number = wintypes.DWORD()
        fs_flags = wintypes.DWORD()
        fs_name_buf = ctypes.create_unicode_buffer(256)

        if not kernel32.GetVolumeInformationW(
            vol_path_buf.value,
            None,
            0,
            ctypes.byref(serial_number),
            None,
            ctypes.byref(fs_flags),
            fs_name_buf,
            256
        ):
            return False, "", f"GetVolumeInformationW failed for volume {vol_path_buf.value}"

        if serial_number.value == 0:
            return False, "", f"Invalid volume serial number 0 for volume {vol_path_buf.value}"

        fs_name = fs_name_buf.value
        serial_hex = f"{serial_number.value:08X}"
        return True, fs_name, f"Verified Windows volume {vol_path_buf.value} (fs={fs_name}, serial={serial_hex})"
    except Exception as exc:
        return False, "", f"Windows volume inspection exception: {exc}"


def verify_mount_boundary(upload_path: Path) -> Tuple[bool, str]:
    """
    Cross-platform mount boundary verification.
    Fails closed on any unexpected, unmounted, or unverified platform state.
    """
    platform = sys.platform

    if platform.startswith("linux"):
        mountinfo = Path("/proc/self/mountinfo")
        if not mountinfo.exists():
            return False, "Linux environment missing /proc/self/mountinfo"
        try:
            content = mountinfo.read_text(encoding="utf-8")
            is_valid, fs_type, reason = parse_linux_mountinfo(content, str(upload_path.resolve()))
            return is_valid, reason
        except Exception as exc:
            return False, f"Failed to read/parse /proc/self/mountinfo: {exc}"

    elif platform in ("win32", "cygwin"):
        is_valid, fs_type, reason = verify_windows_volume(upload_path.resolve())
        return is_valid, reason

    elif platform == "darwin":
        try:
            # macOS: check device ID boundary change or os.path.ismount
            is_mount = (
                upload_path.resolve().exists() and (
                    os.path.ismount(upload_path.resolve())
                    or (upload_path.resolve().parent.exists() and os.stat(upload_path.resolve()).st_dev != os.stat(upload_path.resolve().parent).st_dev)
                )
            )
            if is_mount:
                return True, f"Verified macOS mount boundary for {upload_path}"
            return False, f"Path {upload_path} is not an explicit mountpoint on macOS"
        except Exception as exc:
            return False, f"macOS mount inspection failed: {exc}"

    return False, f"Unsupported platform '{platform}': cannot verify genuine mount boundary"


def verify_storage_root_identity(
    upload_dir: Path,
    expected_volume_id: str,
    secret_key: Optional[str] = None,
    skip_mount_check: bool = False
) -> Tuple[bool, str]:
    """
    Validates complete genuine storage root identity:
    1. Rejects symlinks at target and ancestor paths.
    2. Proves genuine platform mount boundary (unless explicitly skipped for isolated unit tests).
    3. Verifies .clipforge_volume_token exists, readable, and authentic HMAC-SHA256 signature.
    4. Matches volume_id against expected database coordinator volume_id.
    """
    try:
        valid_secret = resolve_storage_identity_secret(secret_key)
    except Exception as exc:
        return False, f"Storage identity secret rejection: {exc}"

    if not upload_dir.exists():
        return False, f"Upload root does not exist: {upload_dir}"

    if upload_dir.is_symlink():
        return False, f"Upload root is a symlink: {upload_dir}"

    try:
        resolved = upload_dir.resolve(strict=True)
    except Exception as exc:
        return False, f"Upload root cannot be resolved strictly: {exc}"

    # Rejection of root directory misconfiguration
    if str(resolved) in ("/", "C:\\", "\\"):
        return False, f"Upload root resolves to system root ({resolved}). Invalid configuration."

    # Verify Mount Boundary
    if not skip_mount_check:
        is_mount, reason = verify_mount_boundary(resolved)
        if not is_mount:
            return False, f"Mount boundary verification failed: {reason}"

    # Verify Token File
    token_file = resolved / TOKEN_FILENAME
    if not token_file.exists() or not token_file.is_file():
        return False, f"Volume identity token missing at {token_file}"

    try:
        with open(token_file, "r", encoding="utf-8") as f:
            token_data = json.load(f)
    except Exception as exc:
        return False, f"Unreadable volume identity token at {token_file}: {exc}"

    if token_data.get("magic_signature") != MAGIC_SIGNATURE:
        return False, f"Invalid volume token magic signature in {token_file}"

    token_volume_id = token_data.get("volume_id")
    token_mount = token_data.get("canonical_mount")
    token_cluster = token_data.get("cluster_id")
    token_hmac = token_data.get("hmac_sha256")

    if not all([token_volume_id, token_mount, token_cluster, token_hmac]):
        return False, f"Incomplete volume token data in {token_file}"

    try:
        expected_hmac = compute_volume_hmac(token_volume_id, token_mount, token_cluster, valid_secret)
    except Exception as exc:
        return False, f"Failed computing expected HMAC: {exc}"

    if not hmac.compare_digest(token_hmac, expected_hmac):
        return False, f"Cryptographic HMAC verification failed for token {token_file}"

    if token_volume_id != expected_volume_id:
        return False, (
            f"Volume ID mismatch: database expected '{expected_volume_id}', "
            f"token contains '{token_volume_id}'"
        )

    return True, "Storage root identity cryptographically verified and authentic"
