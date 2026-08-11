from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, model_validator


class PersonalKeyInput(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    provider: str = Field(min_length=2, max_length=50)
    model: str = Field(min_length=1, max_length=120)
    api_key: SecretStr
    api_base_url: AnyHttpUrl | None = None


class ImageInput(BaseModel):
    mime_type: Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
    data: str = Field(min_length=4, max_length=4_200_000)


class DocumentInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=2, max_length=120)
    data: str = Field(min_length=4, max_length=20_000_000)


class CodeFileInput(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=2_000_000)
    language: str | None = Field(default=None, max_length=40)


class ChatInput(BaseModel):
    content: str = Field(default="", max_length=50000)
    images: list[ImageInput] = Field(default_factory=list, max_length=4)
    documents: list[DocumentInput] = Field(default_factory=list, max_length=4)
    code_files: list[CodeFileInput] = Field(default_factory=list, max_length=50)
    key_id: int | None = Field(default=None, ge=1)
    key_source: Literal["personal", "organization"] | None = None

    @model_validator(mode="after")
    def requires_content_or_image(self):
        if not self.content.strip() and not self.images and not self.documents and not self.code_files:
            raise ValueError("Write a message or attach a file.")
        return self


class RenameInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class FileInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = ""
    language: str = Field(default="plaintext", max_length=50)


class FileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    language: str | None = Field(default=None, max_length=50)
