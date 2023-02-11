from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
import aiofiles

import glob
from typing import List

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.models import UserInDB

from app.config import log


import os
import mimelib  # problem is with VSCode local resolution, in the Docker container we're fine. 
import json


router = APIRouter()

# ------------------------------------------------------------------------------------------------------------------
# endpoint for general uploads, restricted to admin accounts, once uploaded downloads are not restricted
@router.post("/", status_code=200)
async def upload(file: UploadFile = File(...), 
                 current_user: UserInDB = Depends(get_current_active_user)):
    
    # u = os.path.expanduser('~')
    # log.info(f"upload: {u}")
    
    if not user_has_role(current_user,"admin") and not user_has_role(current_user,"staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail="Not Authorized to upload files")
        
    try:
        upload_path = config.get_base_path() / 'static/uploads' / file.filename
        #
        log.info(f"upload: attempting {upload_path}")
        #
        async with aiofiles.open(upload_path, 'wb') as f:
            log.info(f"upload: file opened for writing...")
            CHUNK_SIZE = 1024*1024
            while contents := await file.read(CHUNK_SIZE):
                await f.write(contents)
                
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        await file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


# ------------------------------------------------------------------------------------------------------------------
# endpoint for project uploads, restricted to users with that project's access
@router.post("/{projectname}", status_code=200)
async def project_upload(projectname: str, 
                         file: UploadFile = File(...), 
                         current_user: UserInDB = Depends(get_current_active_user)):
        
    proj = await crud.get_project_by_name( projectname )
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    if proj.status == 'archived':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived projects cannot receive uploads")
        
    tag = await crud.get_tag( proj.tagid )
    if not proj:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    
    log.info( f"project_upload: isAdmin is {isAdmin}, isProjMember is {isProjMember}")
    
    if not isAdmin and not isProjMember:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail=f"Not Authorized to upload {projectname} files") 
    
    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    log.info(f"project_upload: about to try...")
    
    try:
        upload_path = config.get_base_path() / 'static/uploads' / tag.text / file.filename
        #
        log.info(f"upload: attempting {upload_path}")
        #
        async with aiofiles.open(upload_path, 'wb') as f:
            log.info(f"upload: file opened for writing...")
            CHUNK_SIZE = 1024*1024
            while contents := await file.read(CHUNK_SIZE):
                await f.write(contents)
                
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        await file.close()

    return {"message": f"Successfully uploaded {projectname} {file.filename}"}

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a str subtype. See import of List top of file. 
# Returns a list of files in the unrestricted uploads directory
@router.get("/", response_model=List)
async def read_all_uploads(current_user: UserInDB = Depends(get_current_active_user)) -> List:
    
    # log.info(f"read_all_uploads: here!")
    
    if not user_has_role(current_user,"admin") and not user_has_role(current_user,"staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    upload_path = config.get_base_path() / 'static/uploads/*' 
    
    # log.info(f"read_all_uploads: upload_path {upload_path}")
    
    # result = await glob.glob(upload_path)
    
    result = []
    result.extend(glob.glob(str(upload_path)))
    
    ret = []
    for longPath in result:
        # make sure longPath is not a directory or something weird like a socket or device file
        if os.path.isfile(longPath):
            parts = longPath.split('/')
            count = len(parts)
            filename = parts[count-1]
        
            parts = filename.split('.')
            count = len(parts)
            # ext = parts[count-1]
            # extValid =  count > 1
        
            mo = mimelib.url(longPath)
        
            link = '/static/uploads/' + filename
        
            fdesc = {
                "filename": filename,
                "type": mo.file_type,
                "link": link
            }
        
            ret.append( fdesc )
        
    # log.info(f"read_all_uploads: returning {ret}")
    
    return ret


# ----------------------------------------------------------------------------------------------
@router.get("/{projectname}", response_model=List)
async def read_all_project_uploads(projectname: str, 
                                   current_user: UserInDB = Depends(get_current_active_user)) -> List:
    
    log.info(f"read_all_project_uploads: here!")
    
    proj = await crud.get_project_by_name( projectname )
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    tag = await crud.get_tag( proj.tagid )
    if not proj:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    
    log.info( f"project_upload: isAdmin is {isAdmin}, isProjMember is {isProjMember}")
    
    if not isAdmin and not isProjMember:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'archived' and not isAdmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if project is published, user must be admin or project member
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # finally...
    upload_path = config.get_base_path() / 'static/uploads' / tag.text / '*' 
    
    log.info(f"read_all_project_uploads: upload_path {upload_path}")
    
    result = []
    result.extend(glob.glob(str(upload_path)))
    
    ret = []
    for longPath in result:
        if os.path.isfile(longPath):
            parts = longPath.split('/')
            count = len(parts)
            filename = parts[count-1]
        
            parts = filename.split('.')
            count = len(parts)
        
            # returns mimeObject:
            mo = mimelib.url(longPath)
        
            link = '/static/uploads/' + tag.text + '/' + filename
        
            fdesc = {
                "filename": filename,
                "type": mo.file_type,
                "link": link
            }
        
            ret.append( fdesc )
        
    log.info(f"read_all_project_uploads: returning {ret}")
    
    return ret