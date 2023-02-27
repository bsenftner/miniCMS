from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

import glob
from typing import List
from pathlib import Path

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a str subtype. See import of List top of file. 
@router.get("/", response_model=List[str])
async def read_all_backups(current_user: UserInDB = Depends(get_current_active_user)) -> List[str]:
    
    if not user_has_role(current_user,"admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('NONADMIN_REQUESTED_BACKUPS_LIST'), "" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,  detail="Not Authorized")
    
    backups_path = config.get_base_path() / 'backups/*.gz' 
    
    result = []
    result.extend(glob.glob(str(backups_path)))
    
    ret = []
    for longPath in result:
        parts = longPath.split('/')
        count = len(parts)
        ret.append( parts[count-1] )
    
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('ADMIN_GET_BACKUPS_LIST'), "" )
    
    return ret

# ----------------------------------------------------------------------------------------------
# get the requested file (remember this endpoint is exposed with the prefix "/backups" )
@router.get("/{expected_filename}", status_code=200)  
async def read_backup(expected_filename: str, current_user: UserInDB = Depends(get_current_active_user)):
    
    if not user_has_role(current_user,"admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('NONADMIN_REQUESTED_BACKUP'), "" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")
    
    backup_path = config.get_base_path() / 'backups' /  expected_filename
    
    backup_info = Path(backup_path)
    if not backup_info.is_file():
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_ADMIN_REQUESTED_BACKUP'), "File Not Found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File Not Found")
        
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('ADMIN_GET_BACKUP'), expected_filename )
    
    return FileResponse(backup_path)
