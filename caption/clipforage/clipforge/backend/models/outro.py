"""
Pydantic Schemas for Destination Outros & Multi-Channel Routing.
Covers metadata, API requests, upload payloads, and enriched channel responses.
"""
from enum import Enum
from pydantic import BaseModel, Field


class OutroType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"


class OutroMetadata(BaseModel):
    id: str = Field(..., description="Unique UUID identifier of the outro asset")
    channel_id: str = Field(..., description="Destination channel UUID")
    file_path: str = Field(..., description="Relative storage path under uploads/outros/")
    original_filename: str | None = Field(None, description="Original filename uploaded by user")
    file_size_bytes: int | None = Field(None, description="Asset file size in bytes")
    outro_type: str = Field(..., description="'video' or 'image'")
    duration_seconds: float = Field(..., description="Display/playback duration in seconds")
    width: int | None = Field(None, description="Asset pixel width")
    height: int | None = Field(None, description="Asset pixel height")
    fps: float | None = Field(None, description="Video frames per second")
    has_audio: bool = Field(False, description="Whether the video track includes audio")
    version: int = Field(1, description="Sequential version number for this channel")
    is_active: bool = Field(True, description="Whether this outro is currently active")
    preview_url: str = Field(..., description="Endpoint URL to stream or preview the outro asset")
    created_at: str | None = Field(None, description="ISO formatted creation timestamp")
    updated_at: str | None = Field(None, description="ISO formatted last update timestamp")


class OutroResponse(BaseModel):
    status: str = Field("success", description="Status string")
    channel_id: str = Field(..., description="Destination channel UUID")
    outro: OutroMetadata = Field(..., description="Active outro metadata")


class OutroUploadResponse(BaseModel):
    status: str = Field("success", description="Status string")
    message: str = Field("Outro successfully uploaded and configured", description="Human-readable status")
    channel_id: str = Field(..., description="Destination channel UUID")
    outro: OutroMetadata = Field(..., description="Created outro metadata")


class OutroDeleteResponse(BaseModel):
    status: str = Field("success", description="Status string")
    channel_id: str = Field(..., description="Destination channel UUID")
    message: str = Field("Outro successfully removed", description="Human-readable status")


class DestinationChannelOutroSummary(BaseModel):
    id: str
    youtube_channel_id: str
    channel_name: str
    has_outro: bool
    active_outro: OutroMetadata | None = None
