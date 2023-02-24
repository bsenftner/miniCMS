# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for "user action" posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status
from fastapi.responses import JSONResponse

from app.api import crud 
from app.api.users import get_current_active_user, user_has_role, UserAction
from app.api.models import UserInDB, UserActionDB, UserActionResponse
from app.api.utils import convertDateToLocal

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=UserActionResponse)
async def read_user_action(id: int = Path(..., gt=0),
                           current_user: UserInDB = Depends(get_current_active_user)) -> UserActionResponse:
    
    if not user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get single user action {id}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")
    
    action: UserActionDB = await crud.get_user_action(id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    
    local_dt = convertDateToLocal( action.created_date )
    retAction = UserActionResponse(
                    action=UserAction[action.actionCode],
                    username=current_user.username,
                    description=action.description,
                    created_date=local_dt.strftime("%c")
                )
    
    return retAction

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a UserActionResponse subtype. See import of List top of file. 
@router.get("/", response_model=List[UserActionResponse])
async def read_all_user_actions(current_user: UserInDB = Depends(get_current_active_user)) -> List[UserActionResponse]:
    
    if not user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       "tried to get all user actions" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")
    
    # get all user actions:
    actionList = await crud.get_all_user_actions()
    
    userList = await crud.get_all_users()
    
    retList = []
    for a in actionList:
        for u in userList:
            if a.userid==u.userid:
                local_dt = convertDateToLocal( a.created_date )
                retAction = UserActionResponse(
                    action=UserAction[a.actionCode],
                    username=u.username,
                    description=a.description,
                    created_date=local_dt.strftime("%c")
                )
        retList.append(retAction)
        
    return retList

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a UserActionDB subtype. See import of List top of file. 
@router.get("/user/{userid}/{limit}/{offset}", response_model=List[UserActionResponse])
async def read_all_this_users_actions(userid: int, limit: int,  offset: int,
                                      current_user: UserInDB = Depends(get_current_active_user)) -> List[UserActionResponse]:
    
    
    user = await crud.get_user_by_id(userid)
    
    if not user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get user actions of {user.userid}, {user.username}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

    
    # get all the actions of this user:
    actionList = await crud.get_all_this_users_actions(user, limit, offset)
    
    retList = []
    for a in actionList:
        # the app runs in UTC local time:
        local_dt = convertDateToLocal( a.created_date )
        retAction = UserActionResponse(
            action=UserAction[a.actionCode],
            username=user.username,
            description=a.description,
            created_date=local_dt.strftime("%c")
        )
        retList.append(retAction)
        
    return retList


# ----------------------------------------------------------------------------------------------
# The response_model is the number of user actions created by the requested user by userid 
@router.get("/count/{userid}")
async def count_all_this_users_actions(userid: int,
                                      current_user: UserInDB = Depends(get_current_active_user)):
    
    user = await crud.get_user_by_id(userid)
    
    if not user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get user actions of {user.userid}, {user.username}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

    
    # get all the actions of this user:
    count = await crud.get_this_users_action_count(user)
        
    # log.info(f"count_all_this_users_actions: count is {count}")
    
    return JSONResponse(content={"count": count})
