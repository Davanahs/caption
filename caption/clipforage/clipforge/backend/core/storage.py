import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
import boto3
from botocore.exceptions import ClientError
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)


class StorageProvider:
    """Base interface for all storage providers."""

    def put(self, key: str, local_filepath: str) -> None:
        raise NotImplementedError

    def get(self, key: str, dest_path: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def metadata(self, key: str) -> Dict:
        raise NotImplementedError

    def list_prefix(self, prefix: str) -> List[str]:
        raise NotImplementedError

    def get_local_path(self, key: str) -> Optional[Path]:
        """Returns the physical local path if the provider is local, else None."""
        return None

    def checksum(self, filepath: str) -> str:
        """Helper to calculate SHA256 of a local file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                sha256.update(block)
        return sha256.hexdigest()


class LocalStorageProvider(StorageProvider):
    def __init__(self, upload_dir: Path, output_dir: Path):
        self.upload_dir = upload_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        """Safely resolve the key relative to the appropriate base directory based on prefix, preventing path traversal."""
        safe_key = key.lstrip("/")
        
        if safe_key.startswith("outputs/"):
            sub_key = safe_key[8:].lstrip("/")
            base = self.output_dir
        elif safe_key.startswith("uploads/"):
            sub_key = safe_key[8:].lstrip("/")
            base = self.upload_dir
        else:
            # Legacy keys (without explicit roots) default to UPLOAD_DIR
            sub_key = safe_key
            base = self.upload_dir
            
        path = (base / sub_key).resolve()
        # Verify the resolved path is actually inside base directory
        if not str(path).startswith(str(base)):
            raise ValueError(f"Path traversal detected for key: {key}")
        return path

    def put(self, key: str, local_filepath: str) -> None:
        dest_path = self._resolve_path(key)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_filepath, dest_path)

    def get(self, key: str, dest_path: str) -> None:
        src_path = self._resolve_path(key)
        if not src_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)

    def exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()

    def delete(self, key: str) -> None:
        target = self._resolve_path(key)
        if target.exists():
            target.unlink()

    def metadata(self, key: str) -> Dict:
        target = self._resolve_path(key)
        if not target.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        
        stat = target.stat()
        return {
            "size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "updated_at": stat.st_mtime,
        }

    def list_prefix(self, prefix: str) -> List[str]:
        # Handle empty prefix (used by orphan detection)
        if not prefix or prefix == "/":
            results = []
            for root, _, files in os.walk(self.upload_dir):
                for f in files:
                    full_path = Path(root) / f
                    results.append(f"uploads/{full_path.relative_to(self.upload_dir).as_posix()}")
            for root, _, files in os.walk(self.output_dir):
                for f in files:
                    full_path = Path(root) / f
                    results.append(f"outputs/{full_path.relative_to(self.output_dir).as_posix()}")
            return results

        # Prefix is non-empty. Use safe resolution.
        try:
            prefix_path = self._resolve_path(prefix)
        except ValueError:
            return [] # Invalid prefix or traversal
        
        # Determine the logical base prefix for results
        safe_key = prefix.lstrip("/")
        if safe_key.startswith("outputs/"):
            logical_prefix = "outputs/"
            base = self.output_dir
        elif safe_key.startswith("uploads/"):
            logical_prefix = "uploads/"
            base = self.upload_dir
        else:
            logical_prefix = ""
            base = self.upload_dir

        # If the prefix itself is a file
        if prefix_path.is_file():
            return [prefix]
        
        results = []
        
        # If it's a directory, return all recursive files under it
        if prefix_path.is_dir():
            for root, _, files in os.walk(prefix_path):
                for f in files:
                    full_path = Path(root) / f
                    rel_to_base = full_path.relative_to(base).as_posix()
                    results.append(f"{logical_prefix}{rel_to_base}")
            return results

        # Prefix is an incomplete string (e.g. "outputs/123/sou")
        # Walk the base directory and filter
        for root, _, files in os.walk(base):
            for f in files:
                full_path = Path(root) / f
                rel_to_base = full_path.relative_to(base).as_posix()
                full_logical_key = f"{logical_prefix}{rel_to_base}"
                if full_logical_key.startswith(safe_key):
                    results.append(full_logical_key)
                    
        return results

    def get_local_path(self, key: str) -> Optional[Path]:
        try:
            return self._resolve_path(key)
        except ValueError:
            return None


class S3StorageProvider(StorageProvider):
    def __init__(self):
        client_kwargs = {
            "service_name": "s3",
            "region_name": settings.S3_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
            client_kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY
            client_kwargs["aws_secret_access_key"] = settings.S3_SECRET_KEY

        self.s3 = boto3.client(**client_kwargs)
        self.bucket = settings.S3_BUCKET_NAME

    def put(self, key: str, local_filepath: str) -> None:
        try:
            self.s3.upload_file(local_filepath, self.bucket, key)
        except ClientError as e:
            logger.error(f"Failed to upload {key} to S3: {e}")
            raise

    def get(self, key: str, dest_path: str) -> None:
        try:
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            self.s3.download_file(self.bucket, key, dest_path)
        except ClientError as e:
            logger.error(f"Failed to download {key} from S3: {e}")
            raise

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def delete(self, key: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            logger.error(f"Failed to delete {key} from S3: {e}")
            raise

    def metadata(self, key: str) -> Dict:
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)
            return {
                "size_bytes": response.get('ContentLength', 0),
                "created_at": response.get('LastModified'),
                "content_type": response.get('ContentType'),
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Key not found: {key}")
            raise

    def list_prefix(self, prefix: str) -> List[str]:
        keys = []
        paginator = self.s3.get_paginator('list_objects_v2')
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    keys.append(obj['Key'])
            return keys
        except ClientError as e:
            logger.error(f"Failed to list prefix {prefix} in S3: {e}")
            raise


class StorageService:
    def __init__(self):
        self.backend_type = settings.STORAGE_BACKEND
        
        if self.backend_type == "s3":
            self.provider = S3StorageProvider()
        else:
            self.provider = LocalStorageProvider(upload_dir=settings.UPLOAD_DIR, output_dir=settings.OUTPUT_DIR)

    def put(self, key: str, local_filepath: str) -> None:
        self.provider.put(key, local_filepath)

    def get(self, key: str, dest_path: str) -> None:
        self.provider.get(key, dest_path)

    def exists(self, key: str) -> bool:
        return self.provider.exists(key)

    def delete(self, key: str) -> None:
        self.provider.delete(key)

    def metadata(self, key: str) -> Dict:
        return self.provider.metadata(key)

    def list_prefix(self, prefix: str) -> List[str]:
        return self.provider.list_prefix(prefix)
        
    def checksum(self, filepath: str) -> str:
        return self.provider.checksum(filepath)

    def get_local_path(self, key: str) -> Optional[Path]:
        if hasattr(self.provider, "get_local_path"):
            return self.provider.get_local_path(key)
        return None

# Singleton instance
storage_service = StorageService()
