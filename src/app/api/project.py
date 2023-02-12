# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for project posts, handling the CRUD operations with the db 
#
import os

from fastapi import APIRouter, HTTPException, Path, Depends, status

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB, basicTextPayload, ProjectRequest, ProjectUpdate, ProjectSchema, ProjectDB

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=ProjectDB, status_code=201)
async def create_project(payload: ProjectRequest, 
                         current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
    
    log.info(f"create_project: received {payload}")
    
    if not user_has_role(current_user, "admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to create Projects")
    
    # project tag must be all letters or numbers, no spaces or puncuation 
    # (going to be used as directory name as well as an access role name)
    if payload.tag.isalnum() is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                            detail="Bad Project Tag, only use letters and numbers in Project Tags.")
    
    proj = await crud.get_project_by_name( payload.name )
    if proj is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Project with this name already exists.")
    
    # a tag with the project name needs to also exist, so verify a tag with the requested project name does not exist yet:
    tag = await crud.get_tag_by_name( payload.tag )
    if tag is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Tag with this name already exists.")
   
    # good, we can create the project AFTER we create a tag with the project tag:
    tagPayload = basicTextPayload( text=payload.tag )
    tagid = await crud.post_tag( tagPayload )
    if tagid is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Dependant data creation failure.")

    # projects all receive their own upload directory with the name of the tag text
    # proj_upload_path = config.get_base_path() / 'static/uploads' / payload.tag
    proj_upload_path = config.get_base_path() / 'uploads' / payload.tag
    if not os.path.exists(proj_upload_path):
        log.info(f"create_project: creating project upload directory {proj_upload_path}")
        os.makedirs(proj_upload_path)
   
    projPayload = ProjectSchema(name=payload.name,
                                text=payload.text,
                                userid=current_user.userid,
                                username=current_user.username,
                                status="unpublished",
                                tagid=tagid)
    projectid = await crud.post_project(projPayload)
    log.info(f"create_project: returning id {projectid}")
    response_object = {
        "projectid": projectid,
        "name": projPayload.name, 
        "text": projPayload.text,
        "userid": projPayload.userid,
        "username": projPayload.username,
        "status": projPayload.status,
        "tagid": projPayload.tagid
    }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=ProjectDB)
async def read_project(id: int = Path(..., gt=0),
                       current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
    
    log.info("read_project: here!!")
    
    proj: ProjectDB = await crud.get_project(id)
    
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    return proj

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a ProjectDB subtype. See import of List top of file. 
# Returns a list of the projects the user has access.
@router.get("/", response_model=List[ProjectDB])
async def read_all_projects(current_user: UserInDB = Depends(get_current_active_user)) -> List[ProjectDB]:
    # get all the projects this user has access:
    projList = await crud.get_all_projects(current_user)
    return projList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{id}", response_model=ProjectDB)
async def update_project(payload: ProjectUpdate, 
                         id: int = Path(..., gt=0), 
                         current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
   
    log.info("update_project: here!!")

    proj: ProjectDB = await crud.get_project(id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
        
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to access project.")

    putPayload = ProjectSchema(
        name=payload.name, 
        text=payload.text, 
        userid=proj.userid,             # retaining original author
        username=proj.username,
        status=payload.status,
        tagid=proj.tagid                # do not allow tagid to change
    )
    projectid = await crud.put_project(id, putPayload)
    
    response_object = {
                "projectid": projectid,
                "name": putPayload.name, 
                "text": putPayload.text,
                "userid": putPayload.userid,
                "username": putPayload.username,
                "status": putPayload.status,
                "tagid": putPayload.tagid
            }
    return response_object

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=ProjectDB)
async def delete_project(id: int = Path(..., gt=0), 
                         current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
    
    if not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to delete Projects")
    
    project: ProjectDB = await crud.get_project(id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # at this location we need code to:
    # 1) get all memos associated with this project 
    # 2) delete them one by one (which also deletes their comments)
    # 3) finally delete the project itself 
    #
    # NOTE: what about uploaded files?
    # TODO: 1) make uploads go into a project specific project directory 
    #           seems to work
    # TODO: 2) create a project directory for any uploads to be saved into   
    #           seems to work 
    # TODO: 3) make all memos belong to a project 
    
    await crud.delete_project(id)

    return project
