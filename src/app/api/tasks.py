# ---------------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for one barebones Celery Task
#

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.users import get_current_active_user
from app.api.models import UserInDB, basicTextPayload

from app.config import log


# Celery specific:
from app.worker import create_task
from celery.result import AsyncResult


# the "task" router
router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", status_code=201)
async def run_task(payload: basicTextPayload, 
                   current_user: UserInDB = Depends(get_current_active_user)):
    
    log.info(f"run_task: payload is {payload.text}")
    
    task_type = payload.text
    task = create_task.delay(int(task_type))
    
    log.info(f"run_task: task_id is {task.id}")
    
    return JSONResponse({"task_id": task.id})

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{task_id}")
async def get_task_status(task_id: str,
                          current_user: UserInDB = Depends(get_current_active_user)):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return JSONResponse(result)
