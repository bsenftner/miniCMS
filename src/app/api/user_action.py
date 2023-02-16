# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for "user action" posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud, users
from app.api.users import get_current_active_user, user_has_role, UserAction
from app.api.models import UserInDB, basicTextPayload, UserActionDB, UserActionResponse

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=UserActionResponse)
async def read_user_action(id: int = Path(..., gt=0),
                           current_user: UserInDB = Depends(get_current_active_user)) -> UserActionResponse:
    
    if not users.user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get single user action {id}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")
    
    action: UserActionDB = await crud.get_user_action(id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    
    retAction = UserActionResponse(
                    action=UserAction[action.actionCode],
                    username=current_user.username,
                    description=action.description,
                    created_date=action.created_date
                )
    
    return retAction

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a UserActionResponse subtype. See import of List top of file. 
@router.get("/", response_model=List[UserActionResponse])
async def read_all_user_actions(current_user: UserInDB = Depends(get_current_active_user)) -> List[UserActionResponse]:
    
    if not users.user_has_role( current_user, 'admin' ):
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
                retAction = UserActionResponse(
                    action=UserAction[a.actionCode],
                    username=u.username,
                    description=a.description,
                    created_date=a.created_date
                )
        retList.append(retAction)
        
    return retList

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a UserActionDB subtype. See import of List top of file. 
@router.get("/user/{userid}", response_model=List[UserActionResponse])
async def read_all_this_users_actions(userid: int,
                                      current_user: UserInDB = Depends(get_current_active_user)) -> List[UserActionResponse]:
    
    
    user = await crud.get_user_by_id(userid)
    
    if not users.user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get user actions of {user.userid}, {user.username}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

    
    # get all the actions of this user:
    actionList = await crud.get_all_this_users_actions(user)
    
    retList = []
    for a in actionList:
        retAction = UserActionResponse(
            action=UserAction[a.actionCode],
            username=user.username,
            description=a.description,
            created_date=a.created_date
        )
        retList.append(retAction)
        
    return retList
