# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for memo posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, MemoDB, MemoSchema, MemoResponse, ProjectDB, TagDB

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=MemoResponse, status_code=201)
async def create_memo(payload: MemoSchema, 
                      current_user: UserInDB = Depends(get_current_active_user)) -> MemoResponse:
    
    proj: ProjectDB = await crud.get_project(payload.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_MEMO'), 
                                       f"Project {payload.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Memo Project not found")
        
    tag: TagDB = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_MEMO'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Memo Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_MEMO'), 
                                       f"Project {proj.projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create memo for project.")
    
    if not tag.text in payload.tags:
        payload.tags += ' '
        payload.tags += tag.text
    
    memoid = await crud.post_memo(payload, current_user.userid)

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('POST_NEW_MEMO'), 
                                   f"memo {memoid}, '{payload.title}'" )
    
    return { "memoid": memoid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=MemoDB)
async def read_memo(id: int = Path(..., gt=0),
                    current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
    
    memo = await crud.get_memo(id)
    if memo is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_MEMO'), 
                                       f"Memo {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    
    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_MEMO'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_MEMO'), 
                                   f"memo {memo.memoid}, '{memo.title}'" )
     
    return memo

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a MemoDB subtype. See import of List top of file. 
@router.get("/", response_model=List[MemoDB])
async def read_all_memos(current_user: UserInDB = Depends(get_current_active_user)) -> List[MemoDB]:
    
    # get all the memos, they are filtered by the user's roles:
    memoList = await crud.get_all_memos( current_user )
            
    return memoList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{id}", response_model=MemoResponse)
async def update_memo(payload: MemoSchema, 
                      id: int = Path(..., gt=0), 
                      current_user: UserInDB = Depends(get_current_active_user)) -> MemoResponse:
   
    # log.info("update_memo: here!!")

    memo: MemoDB = await crud.get_memo(id)
    if memo is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_MEMO'), 
                                       f"Memo {id}, not found" )
        raise HTTPException(status_code=404, detail="Memo not found")
        
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_MEMO'), 
                                       f"Memo Project {memo.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Memo Project not found")
        
    tag: TagDB = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid,
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_MEMO'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Memo Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_UPDATE_MEMO'), 
                                       "Not Authorized for Project" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized for project.")
    
    if memo.userid != current_user.userid and not user_has_role(current_user,"admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_UPDATE_MEMO'), 
                                       "Not Authorized to change other's Memos" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to change other's Memos")
    
    if not tag.text in payload.tags:
        payload.tags += ' '
        payload.tags += tag.text
    
    # make sure to retain original memo author:
    payload.userid = memo.userid
    payload.username = memo.username 
    
    memoid = await crud.put_memo(id, memo.userid, payload)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_MEMO'), 
                                   f"Memo {memo.memoid}, '{memo.title}'" )
    
    return { "memoid": memoid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=MemoDB)
async def delete_memo(id: int = Path(..., gt=0), current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
    
    memo: MemoDB = await crud.get_memo(id)
    if memo is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_DELETE_MEMO'), 
                                       f"Memo {id}, not found" )
        raise HTTPException(status_code=404, detail="Memo not found")

    # note: not verifying project exists or is active;
    # if we are here, the memo exists and the user wants it deleted
    
    if memo.userid != current_user.userid and not user_has_role(current_user,"admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_DELETE_MEMO'), 
                                       "Not Authorized to delete other's Memos" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to delete other's Memos")
        
    memoComments = await crud.get_all_memo_comments(id)
    for mc in memoComments:
        log.info(f"delete_memo: also deleting comment {mc.commid}")
        await crud.delete_comment(mc.commid)
    
    await crud.delete_memo(id)

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('DELETE_MEMO'), 
                                   f"memo {memo.memoid}, '{memo.title}'" )
    
    return memo
