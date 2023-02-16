# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for comment posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role, UserAction
from app.api.models import UserInDB, MemoDB, CommentSchema, CommentDB, CommentResponse

from typing import List

from app.config import log

router = APIRouter()



# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=CommentResponse, status_code=201)
async def create_comment(payload: CommentSchema, 
                         current_user: UserInDB = Depends(get_current_active_user)) -> CommentResponse:
    
    # memo must exist to receive a comment:
    memo = await crud.get_memo(payload.memoid)
    if memo is None:
        await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_POST_NEW_COMMENT'), f"Memo {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    
    # user must have memo access to comment on the memo:
    memo_access = await crud.user_has_memo_access(current_user, memo)
    if not memo_access:
        await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_POST_NEW_COMMENT'), "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    
    if payload.parent == 0:
        payload.parent = None
        log.info(f"create_comment: setting payload.parent to None.")
    else:
        # if the new comment is a reply to another comment of this memo, that parent comment must exist:
        pcomm: CommentDB = await crud.get_comment( payload.parent )
        if pcomm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found.")
    
    # post comment: 
    commid = await crud.post_comment(payload)

    await crud.rememberUserAction( current_user.userid, UserAction.index('POST_NEW_COMMENT'), f"id {commid}" )
    
    return { "commid": commid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=CommentDB)
async def read_comment(id: int = Path(..., gt=0),
                       current_user: UserInDB = Depends(get_current_active_user)) -> CommentDB:
    
    # log.info("read_comment: here!!")
    
    comment: CommentDB = await crud.get_comment(id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    memo = await crud.get_memo(comment.memoid)
    if memo is None:
        if not user_has_role(current_user,"admin"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    else:
        memo_access = await crud.user_has_memo_access(current_user, memo)
        if not memo_access:
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
    
    # log.info(f"read_all_memo_comments: got memo {memo}")
    
    memodb = MemoDB(
        memoid=memo.memoid,
        title=memo.title,
        text=memo.text,
        status=memo.status,
        tags=memo.tags,
        access=memo.access,
        userid=memo.userid,
        username=memo.username,
        projectid=memo.projectid,
        created_date=memo.created_date,
        updated_date=memo.updated_date
    )
    
    # log.info(f"read_all_memo_comments: got memodb {memodb}")
    memo_access = await crud.user_has_memo_access(current_user, memodb)
    if not memo_access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
        
    # get all the comments associated with this memo:
    memoCommentList = await crud.get_all_memo_comments( memodb.memoid )
            
    return memoCommentList

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
        await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_DELETE_COMMENT'), f"Comment {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    memo = await crud.get_memo(comment.memoid)
    if memo is None:
        if not user_has_role(current_user,"admin"):
            await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_DELETE_COMMENT'), f"Comment {id}, No Memo" )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
    else:
        memo_access = await crud.user_has_memo_access(current_user, memo)
        if not memo_access:
            await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_DELETE_COMMENT'), f"Comment {id}, Not Memo Authorized" )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized.")
        
    await crud.delete_comment(id)

    await crud.rememberUserAction( current_user.userid, UserAction.index('DELETE_COMMENT'), f"Comment {id}" )
    
    return comment
