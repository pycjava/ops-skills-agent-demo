from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.memory import (
    delete_memory_document,
    list_memory_tree,
    read_memory_document,
)

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("/tree")
async def get_memory_tree():
    return JSONResponse(await list_memory_tree())


@router.get("/content")
async def get_memory_content(path: str):
    return JSONResponse(await read_memory_document(path))


@router.delete("/content")
async def delete_memory_content(path: str):
    return JSONResponse(await delete_memory_document(path))
