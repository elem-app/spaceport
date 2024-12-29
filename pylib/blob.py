from enum import StrEnum


class Blob:
    def __init__(self, data: bytes):
        self._data = data

    @property
    def view(self) -> memoryview:
        return memoryview(self._data)

    @property
    def bytes(self) -> bytes:
        return self._data


class MultimediaBlob(Blob):
    def __init__(self, data: bytes, media_type: str | None = None):
        super().__init__(data)
        self.media_type = media_type


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
