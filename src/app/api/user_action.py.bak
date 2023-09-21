# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for "user action" posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status
from fastapi.responses import JSONResponse

from app.api import crud 
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB, UserActionDB, UserActionResponse
from app.api.utils import convertDateToLocal

from typing import List

from app.config import log

router = APIRouter()

# essentially severity levels:
# THESE CANNOT BE CHANGED WITHOUT REBUILDING THE DATABASE
UserActionLevel = [
    'SITEBUG',                      # user exposed something that should not happen, not be possible
    'NORMAL', 
    'CONFUSED',                     # user action indicates possible confusion 
    'WARNING',                      # doing things they ought not to be doing 
    'BANNED_ACTION'                 # also a fireable offense 
]
#
# the specifc action the user performed:
UserAction = [
    'CREATE_ACCESS_TOKEN',
    'BAD_USERNAME_OR_PASSWORD',
    'DISABLED_USER_LOGIN_ATTEMPT',
    'REFRESHED_ACCESS_TOKEN',
    'NONADMIN_REQUESTED_USER_LIST',
    'NONADMIN_REQUESTED_CREATE_NEW_USER',
    'BAD_CREATE_NEW_USER_DATA',
    'CREATED_NEW_USER',
    'USER_LOGOUT',
    'FAILED_EMAIL_VERIFY',
    'VERIFIED_EMAIL',
    'UNKNOWN_USER_RESET_PASSWORD_ATTEMPT',
    'UNVERIFIED_USER_PASSWORD_RESET_ATTEMPT',
    'USER_RESET_PASSWORD',
    'NONADMIN_ATTEMPTED_USER_ROLES_ASSIGNMENT',
    'USER_ROLES_ASSIGNMENT',
    'UNVERIFIED_USER_SET_PASSWORD_ATTEMPT',
    'USER_SET_PASSWORD',
    'UNVERIFIED_USER_SET_EMAIL_ATTEMPT',
    'FAILED_USER_SET_EMAIL',
    'USER_SET_EMAIL',
    'FAILED_DISABLE_USER',
    'DISABLE_USER',
    'NONADMIN_USER_ACTION_REQUEST',
    'GET_USER_PROFILE',
    'FAILED_GET_PROJECT',
    'GET_PROJECT',
    'NONMEMBER_ATTEMPTED_GET_PROJECT_MEMBERS',
    'FAILED_EDIT_PROJECT',
    'EDIT_PROJECT',
    'NONADMIN_ATTEMPTED_EDIT_NEW_PROJECT',
    'EDIT_NEW_PROJECT',
    'FAILED_GET_MEMO',
    'GET_MEMO',
    'FAILED_EDIT_MEMO',
    'EDIT_MEMO',
    'FAILED_EDIT_NEW_MEMO',
    'EDIT_NEW_MEMO',
    'GET_OWN_SETTINGS_PAGE',
    'FAILED_POST_NEW_MEMO',
    'POST_NEW_MEMO',
    'FAILED_UPDATE_MEMO',
    'UPDATE_MEMO',
    'FAILED_DELETE_MEMO',
    'DELETE_MEMO',
    'FAILED_POST_NEW_AICHAT',
    'POST_NEW_AICHAT',
    'NEW_AICHAT_PAGE',
    'FAILED_GET_AICHAT',
    'GET_AICHAT',
    'FAILED_UPDATE_AICHAT',
    'UPDATE_AICHAT',
    'FAILED_GET_AICHATLIST',
    'GET_AICHATLIST',
    'FAILED_POST_NEW_PROJECT',
    'POST_NEW_PROJECT',
    'GET_ALL_OWN_PROJECTS',
    'FAILED_UPDATE_PROJECT',
    'UPDATE_PROJECT',
    'FAILED_DELETE_PROJECT',
    'DELETE_PROJECT',
    'ARCHIVED_PROJECT',
    'FAILED_POST_NEW_COMMENT',
    'POST_NEW_COMMENT',
    'FAILED_GET_COMMENT',
    'GET_COMMENT',
    'FAILED_GET_MEMO_COMMENT_LIST',
    'GET_MEMO_COMMENT_LIST',
    'FAILED_DELETE_COMMENT',
    'DELETE_COMMENT',
    'FAILED_FILE_UPLOAD',
    'DELETE_FILE',
    'FAILED_DELETE_FILE',
    'FILE_UPLOADED',
    'FAILED_GET_PROJECT_FILE_LIST',
    'GET_PROJECT_FILE_LIST',
    'FAILED_GET_PROJECT_FILE',
    'GET_PROJECT_FILE',
    'FAILED_PLAY_PROJECT_VIDEO',
    'PLAY_PROJECT_VIDEO',
    'NONADMIN_REQUESTED_BACKUPS_LIST',
    'ADMIN_GET_BACKUPS_LIST',
    'NONADMIN_REQUESTED_BACKUP',
    'FAILED_ADMIN_REQUESTED_BACKUP',
    'ADMIN_GET_BACKUP']

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=UserActionResponse)
async def read_user_action(id: int = Path(..., gt=0),
                           current_user: UserInDB = Depends(get_current_active_user)) -> UserActionResponse:
    
    if not user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get single user action {id}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")
    
    action: UserActionDB = await crud.get_user_action(id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    
    local_dt = convertDateToLocal( action.created_date )
    retAction = UserActionResponse(
                    level=UserActionLevel[action.actionLevel], # convert enum int to enum string
                    action=UserAction[action.actionCode], # convert enum int to enum string
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
                                       UserActionLevel.index('BANNED_ACTION'),
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
                    level=UserActionLevel[a.actionLevel], # convert enum int to enum string
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
                                       UserActionLevel.index('BANNED_ACTION'),
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
            level=UserActionLevel[a.actionLevel], # convert enum int to enum string
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
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('NONADMIN_USER_ACTION_REQUEST'), 
                                       f"tried to get user actions of {user.userid}, {user.username}" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

    
    # get all the actions of this user:
    count = await crud.get_this_users_action_count(user)
        
    log.info(f"count_all_this_users_actions: userid is {user.userid}, count is {count}")
    
    return JSONResponse(content={"count": count})
