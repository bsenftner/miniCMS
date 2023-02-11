# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for memo posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB, MemoDB, MemoSchema, ProjectDB, TagDB

from typing import List

from app.config import log

router = APIRouter()



# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=MemoDB, status_code=201)
async def create_memo(payload: MemoSchema, 
                      current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
    
    log.info(f"create_memo: payload is {payload}")
    
    proj: ProjectDB = await crud.get_project(payload.projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Memo Project not found")
        
    tag: TagDB = await crud.get_tag( proj.tagid )
    if not tag:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail="Memo Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create memo for project.")
    
    if not tag.text in payload.tags:
        payload.tags += ' '
        payload.tags += tag.text
        
    log.info(f"create_memo: posting {payload}")
    
    memoid = await crud.post_memo(payload, current_user.userid)

    log.info(f"create_memo: returning id {memoid}")
    
    response_object = {
        "memoid": memoid,
        "userid": payload.userid,
        "username": payload.username,
        "title": payload.title,
        "text": payload.text,
        "status": payload.status,
        "access": payload.access,
        "tags": payload.tags,
        "projectid": payload.projectid,
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=MemoDB)
async def read_memo(id: int = Path(..., gt=0),
                    current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
    
    log.info("read_memo: here!!")
    
    memo = await crud.get_memo(id)
    if memo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    
    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo.")
    
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
@router.put("/{id}", response_model=MemoDB)
async def update_memo(payload: MemoSchema, 
                      id: int = Path(..., gt=0), 
                      current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
   
    # log.info("update_memo: here!!")

    memo: MemoDB = await crud.get_memo(id)
    if memo is None:
        raise HTTPException(status_code=404, detail="Memo not found")
        
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Memo Project not found")
        
    tag: TagDB = await crud.get_tag( proj.tagid )
    if not tag:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Memo Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized for project.")
    
    if memo.userid != current_user.userid and not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to change other's Memos")
    
    if not tag.text in payload.tags:
        payload.tags += ' '
        payload.tags += tag.text
    
    # make sure to retain original memo author:
    payload.userid = memo.userid
    payload.username = memo.username 
    
    memoid = await crud.put_memo(id, memo.userid, payload)
    
    response_object = {
        "memoid": memoid,
        "userid": payload.userid,                 
        "username": payload.username,
        "title": payload.title,
        "text": payload.text,
        "status": payload.status,
        "access": payload.access,
        "tags": payload.tags,
        "projectid": payload.projectid,
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=MemoDB)
async def delete_memo(id: int = Path(..., gt=0), 
                      current_user: UserInDB = Depends(get_current_active_user)) -> MemoDB:
    memo: MemoDB = await crud.get_memo(id)
    if memo is None:
        raise HTTPException(status_code=404, detail="Memo not found")

    # note: not verifying project exists or is active;
    # if we are here, the memo exists and the user wants it deleted
    
    if memo.userid != current_user.userid and not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to delete other's Memos")
        
    memoComments = await crud.get_all_memo_comments(id)
    for mc in memoComments:
        log.info(f"delete_memo: also deleting comment {mc.commid}")
        await crud.delete_comment(mc.commid)
    
    log.info(f"delete_memo: now deleting memo {id}")
    
    await crud.delete_memo(id)

    return memo
