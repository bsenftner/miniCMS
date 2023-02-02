# ----------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for tag posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB, TagDB, basicTextPayload

from typing import List

from app.config import log

router = APIRouter()



# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=TagDB, status_code=201)
async def create_tag(payload: basicTextPayload, 
                     current_user: UserInDB = Depends(get_current_active_user)) -> TagDB:
    
    log.info(f"create_tag: current_user is {current_user}")
    
    if not user_has_role(current_user,"admin") and not user_has_role(current_user,"staff"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create Tags")
        
    log.info(f"create_tag: posting {payload}")
    
    tagid = await crud.post_tag(payload)

    log.info(f"create_tag: returning id {tagid}")
    
    response_object = {
        "tagid": tagid,
        "text": payload.text,
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=TagDB)
async def read_tag(id: int = Path(..., gt=0),
                   current_user: UserInDB = Depends(get_current_active_user)) -> TagDB:
    
    log.info("read_tag: here!!")
    
    tag = await crud.get_tag(id)
    
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    
    return tag

# ---------------------------------------------------------------------------------------------- 
@router.get("/name/{tagName}", response_model=TagDB)
async def read_tag_by_name(tagName: str,
                           current_user: UserInDB = Depends(get_current_active_user)) -> TagDB:
    
    log.info("read_tag_by_name: here!!")
    
    tag = await crud.get_tag_by_name(tagName)
    
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    
    return tag

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a TagDB subtype. See import of List top of file. 
@router.get("/", response_model=List[TagDB])
async def read_all_tags(current_user: UserInDB = Depends(get_current_active_user)) -> List[TagDB]:
    
    # get all the tags:
    tagList = await crud.get_all_tags()
            
    return tagList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{id}", response_model=TagDB)
async def update_tag(payload: basicTextPayload, 
                     id: int = Path(..., gt=0), 
                     current_user: UserInDB = Depends(get_current_active_user)) -> TagDB:
   
    log.info("update_tag: here!!")

    tag: TagDB = await crud.get_tag(id)

    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
        
    if not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to change Tags")

    tagid = await crud.put_tag(id, payload)
    
    response_object = {
        "tagid": tagid,
        "text": payload.text,
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=TagDB)
async def delete_tag(id: int = Path(..., gt=0), 
                     current_user: UserInDB = Depends(get_current_active_user)) -> TagDB:
    
    tag: TagDB = await crud.get_tag(id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    if not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to delete Tags")
    
    await crud.delete_tag(id)

    return tag
