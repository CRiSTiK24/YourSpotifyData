from fastapi import HTTPException, status


class PlaylistNotFound(HTTPException):
    def __init__(self, playlist_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playlist {playlist_id} not found",
        )
