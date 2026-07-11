from fastapi import HTTPException, status


class ArtistNotFound(HTTPException):
    def __init__(self, artist_name: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artist '{artist_name}' not found",
        )
