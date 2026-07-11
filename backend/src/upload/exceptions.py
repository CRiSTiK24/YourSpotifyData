from fastapi import HTTPException, status


class JobNotFound(HTTPException):
    def __init__(self, job_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Import job {job_id} not found"
        )
