# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for comment posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB, MemoDB, CommentSchema, CommentDB

from typing import List

from app.config import log

router = APIRouter()



# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=CommentDB, status_code=201)
async def create_comment(payload: CommentSchema, 
                         current_user: UserInDB = Depends(get_current_active_user)) -> CommentDB:
    
    # log.info(f"create_comment: current_user is {current_user}")
        
    log.info(f"create_comment: posting {payload}")
    
    # memo must exist to receive a comment:
    memo = await crud.get_memo(payload.memoid)
    if memo is None:
       raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    
    # user must have memo access to comment on the memo:
    if not crud.user_has_memo_access(current_user, memo):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    
    if payload.parent == 0:
        payload.parent = None
        log.info(f"create_comment: setting payload.parent to None.")
    else:
        # if the new comment is a reply to another comment of this memo, that parent comment must exist:
        pcomm: CommentDB = await crud.get_comment( payload.parent )
        if pcomm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found.")
    
    log.info(f"create_comment: doing post...")
    
    # post comment: 
    commid = await crud.post_comment(payload)

    log.info(f"create_comment: returning id {commid}")
    
    response_object = {
        "commid": commid,
        "text": payload.text,
        "memoid": payload.memoid,
        "userid": payload.userid,
        "username": payload.username,
        "parent": payload.parent,
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=CommentDB)
async def read_comment(id: int = Path(..., gt=0),
                       current_user: UserInDB = Depends(get_current_active_user)) -> CommentDB:
    
    log.info("read_comment: here!!")
    
    comment: CommentDB = await crud.get_comment(id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    memo = await crud.get_memo(comment.memoid)
    if memo is None:
        if not user_has_role(current_user,"admin"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    else:
        if not crud.user_has_memo_access(current_user,memo):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    
    return comment

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a CommentDB subtype. See import of List top of file. 
@router.get("/memo/{memoid}", response_model=List[CommentDB])
async def read_all_memo_comments(memoid: int,
                                 current_user: UserInDB = Depends(get_current_active_user)) -> List[CommentDB]:
    
    memo: MemoDB = await crud.get_memo(memoid)
    if memo is None:
       raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    
    log.info(f"read_all_memo_comments: got memo {memo}")
    
    memodb = MemoDB(
        memoid=memo.memoid,
        userid=memo.userid,
        title=memo.title,
        description=memo.description,
        status=memo.status,
        tags=memo.tags,
        access=memo.access
    )
    
    log.info(f"read_all_memo_comments: got memodb {memodb}")
    
    if not crud.user_has_memo_access(current_user, memodb):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
        
    # get all the comments associated with this memo:
    memoList = await crud.get_all_memo_comments( memodb.memoid )
            
    return memoList

# ----------------------------------------------------------------------------------------------
# Note: therer is NO PUT for comments; once created they cannot be changed.
# ----------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=CommentDB)
async def delete_comment(id: int = Path(..., gt=0), 
                         current_user: UserInDB = Depends(get_current_active_user)) -> CommentDB:
    
    log.info("delete_comment: here!!")
    
    comment: CommentDB = await crud.get_comment(id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    memo = await crud.get_memo(comment.memoid)
    if memo is None:
        if not user_has_role(current_user,"admin"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    else:
        if not crud.user_has_memo_access(current_user,memo):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
        
    await crud.delete_comment(id)

    return comment
