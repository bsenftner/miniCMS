from typing import Annotated
from fastapi import APIRouter, Path, File, UploadFile, Depends, HTTPException, status, Form
from fastapi.responses import FileResponse

import aiofiles

import glob
from typing import List

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, ProjectFileDB, ProjectFileCreate, TagDB, ProjectDB, ProjectSchema, basicTextPayload

from app.config import log

from app.api.utils import convertDateToLocal

import os
import mimelib  # problem is with VSCode local resolution, in the Docker container we're fine. 
import json

from datetime import datetime

router = APIRouter()

# ------------------------------------------------------------------------------------------------------------------
# endpoint for general uploads, restricted to admin accounts, once uploaded downloads are not restricted
@router.post("/", status_code=200)
async def upload(file: UploadFile = File(...), 
                 current_user: UserInDB = Depends(get_current_active_user)):
    
    if not user_has_role(current_user,"admin") and not user_has_role(current_user,"staff"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized to upload files")
    
    upload_path = '' # so is available later
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
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Error uploading {file.filename}" )
        return {"message": "There was an error uploading the file"}
    finally:
        await file.close()

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('FILE_UPLOADED'), 
                                   f"Uploaded {upload_path}" )
    
    return {"message": f"Successfully uploaded {file.filename}"}

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



# ------------------------------------------------------------------------------------------------------------------
# endpoint for project uploads, restricted to users with that project's access
# calling this endpoint creates a new projectfile resource, where the filename must be unique to that project and 
# any future operations with that file occur through the projectfile resource. The projectfile resource maintains 
# a "library checkout interface" for file modifications, where a project member "checks out" a projectfile, causing 
# it to be downloaded to that user, and marked as "checked out by username" for other project members. Only that 
# project member (or an admin overriding) can cancel the check out, or upload a new version
@router.post("/{projectid}", status_code=200)
async def upload_projectfile(projectid: int, 
                             file: UploadFile = File(...), 
                             modifiable: str = Form(None),
                             current_user: UserInDB = Depends(get_current_active_user)):
    
    log.info( f"upload_projectfile: file attributes are:")
    temp = vars(file)
    for item in temp:
        # log.info( item, ':', temp[item])
        log.info( item )
    log.info( f"upload_projectfile: modifiable is {modifiable}")
    
    proj, tag = await crud.get_project_and_tag(projectid)
    # proj = await crud.get_project( projectid )
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Project {projectid} Not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    if proj.status == 'archived':
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Project {projectid} Archived" )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived projects cannot receive uploads")
        
    # tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Project Tag {proj.tagid} Not Found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    
    log.info( f"upload_projectfile: isAdmin is {isAdmin}, isProjMember is {isProjMember}")
    
    if not isAdmin and not isProjMember:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not Authorized to upload {tag.text} files") 
    
    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized (Project unpublished)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized (not Project member)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # do not allow duplicates of filename:
    projFile: ProjectFileDB = await crud.get_projectfile_by_filename( file.filename, proj.projectid )
    if projFile:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"filename '{file.filename}' already exists" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    log.info(f"upload_projectfile: about to try...")
    
    # upload_path = config.get_base_path() / 'static/uploads' / tag.text / file.filename
    upload_path = config.get_base_path() / 'uploads' / tag.text / file.filename
    try:
        #
        log.info(f"upload: attempting {upload_path}")
        #
        async with aiofiles.open(upload_path, 'wb') as f:
            log.info(f"upload: file opened for writing...")
            CHUNK_SIZE = 1024*1024
            while contents := await file.read(CHUNK_SIZE):
                await f.write(contents)
                
    except Exception:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Error uploading {file.filename}" )
        return {"message": "There was an error uploading the file"}
    finally:
        await file.close()

    modBool = modifiable == 'true'
    pfc = ProjectFileCreate( filename=file.filename, projectid=projectid, modifiable=modBool )
    pfid = await crud.post_projectfile( pfc, current_user.userid )
    if not pfid:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Error writing to db for {file.filename}" )
        # soas to not leave turds around, delete the just uploaded file:
        os.remove(upload_path)
        return {"message": "There was an error uploading the file"}
    
    # everything worked, remember this moment!
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('FILE_UPLOADED'), 
                                   f"Uploaded {upload_path}" )
    
    return {"message": f"Successfully uploaded {tag.text} {file.filename}"}

# ----------------------------------------------------------------------------------------------
async def check_project_uploads_for_orphans(current_user: UserInDB):
    
    # look inside projectfile uploads directory for project directories unaccounted for... 
    upload_path = config.get_base_path() / 'uploads' / '*' 
    #
    result = []
    result.extend(glob.glob(str(upload_path)))
    #
    for longPath in result:
        
        parts = longPath.split('/')
        count = len(parts)
        filename = parts[count-1]
        
        if os.path.isfile(longPath):
            
            # located a lone file inside what should be a directory only containing other directories: 
            log.info(f"check_project_uploads_for_orphans: found orphan file in project upload dir '{filename}'" )
            
        elif os.path.isdir(longPath):
            dirname = filename
            # we have a directory, could it be a project file directory named with a project tag's text? 
            tag: TagDB = await crud.get_tag_by_name( dirname )
            if tag:
                # we have a tag matching this directory name, do we have a matching project using this tag? 
                proj: ProjectDB = await crud.get_project_by_tagid(tag.tagid)
                if not proj:
                    # there is no project for this directory with a name matching that of a tag, make a project: 
                    newProjName = f"recovered orphaned Project '{dirname}'"
                    projPayload = ProjectSchema(name=newProjName,
                                                text=f"Project recovered from orphaned upload directory '{dirname}' (found tag)",
                                                userid=current_user.userid,
                                                username=current_user.username,
                                                status="unpublished",
                                                tagid=tag.tagid)
                    projectid = await crud.post_project(projPayload)
                    if not projectid:
                        log.info(f"check_project_uploads_for_orphans: failed to create project for orphaned upload dir '{dirname}'!!" )
                    else:
                        log.info(f"check_project_uploads_for_orphans: created project for orphaned upload dir '{dirname}', looking inside..." )
                        proj: ProjectDB = await crud.get_project( projectid )
                        if not proj:
                            log.info(f"check_project_uploads_for_orphans: failed to get just created project {newProjName}")
                        else:
                            # let's look inside:
                            await check_project_upload_directory_for_orphans(dirname, proj, current_user)
                else:
                    # we have a project and a tag for it, let's look inside that directory:
                    await check_project_upload_directory_for_orphans(dirname, proj, current_user)
            else:
                # we have a directory but no tag
                #
                # create a tag using that directory as the tag text:
                tagPayload = basicTextPayload( text=dirname )
                tagid = await crud.post_tag( tagPayload )
                if tagid is None:
                    log.info(f"check_project_uploads_for_orphans: failed to create tag for orphan directory in project upload dir '{dirname}'" )
                else:
                    # we made the tag...
                    # let's peek inside the project upload directory:
                    # we have a project and a tag for it, let's look inside that directory:
                    project_upload_path = config.get_base_path() / 'uploads' / dirname / '*' 
                    #
                    project_upload_fileList = []
                    project_upload_fileList.extend(glob.glob(str(project_upload_path)))
                    #
                    # default recovered project status: 
                    new_status = 'unpublished'
                    # if the directory contains one file, that file is a zip with the name in zip_archive_path, it's an archived project:
                    if len(project_upload_fileList)==1:
                        zip_archive_path = str(config.get_base_path()) + '/uploads/' + dirname + '/project_' + str(dirname) + 'archive.zip'
                        if project_upload_fileList[0] == zip_archive_path:
                            new_status = 'archived'
                    #
                    # ...let's make the project now that the status is established:
                    newProjName = f"recovered orphaned Project '{dirname}'"
                    projPayload = ProjectSchema(name=newProjName,
                                                text=f"Project recovered from orphaned upload directory '{dirname}' (made tag)",
                                                userid=current_user.userid,
                                                username=current_user.username,
                                                status=new_status,
                                                tagid=tagid)
                    projectid = await crud.post_project(projPayload)
                    if not projectid:    
                        log.info(f"check_project_uploads_for_orphans: failed creating project for orphan directory in project upload dir '{dirname}'" )
                    else:
                        proj: ProjectDB = await crud.get_project( projectid )
                        if not proj:
                            log.info(f"check_project_uploads_for_orphans: failed to get just created project {newProjName}")
                        else:
                            # let's look inside:
                            await check_project_upload_directory_for_orphans(dirname, proj, current_user)
                                
# slave to the above routine:
async def check_project_upload_directory_for_orphans(dirname: str, proj: ProjectDB, current_user: UserInDB):
    
    # we have a project and a tag for it, let's look inside that directory:
    project_upload_path = config.get_base_path() / 'uploads' / dirname / '*' 
    #
    project_upload_result = []
    project_upload_result.extend(glob.glob(str(project_upload_path)))
    #
    for proj_upload_file_path in project_upload_result:
        #
        puparts = proj_upload_file_path.split('/')
        pucount = len(puparts)
        pufname = puparts[pucount-1]
        #
        if os.path.isfile(proj_upload_file_path):
            pfid = await crud.get_projectfile_by_filename( pufname, proj.projectid )
            if not pfid:
                # located an untracked file inside that recovered project upload directory, let's recover the file too:
                pfc = ProjectFileCreate( filename=pufname, projectid=proj.projectid, modifiable=True ) 
                pfid = await crud.post_projectfile( pfc, current_user.userid )
                if not pfid:
                    log.info(f"check_project_upload_directory_for_orphans: failed recovering orphaned file '{pufname}' for project '{proj.name}'")
                else:
                    log.info(f"check_project_upload_directory_for_orphans: recovered orphaned file '{pufname}' for project '{proj.name}'")
            else:
                log.info(f"check_project_upload_directory_for_orphans: noticed and validated file '{pufname}' for project '{proj.name}'")
                
        elif os.path.isdir(proj_upload_file_path):
            # we've got a directory within a project upload directory that is untracked:
            log.info(f"check_project_upload_directory_for_orphans: orphaned directory inside project upload dir at '{proj_upload_file_path}'")
    
# ----------------------------------------------------------------------------------------------
# returns a list of the projectfiles for the passed project via it's projectid 
@router.get("/{projectid}", response_model=List)
async def get_project_projectfiles(projectid: int, 
                                   current_user: UserInDB = Depends(get_current_active_user)) -> List:
    
    proj, tag = await crud.get_project_and_tag(projectid)
    # proj = await crud.get_project( projectid )
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       f"Project {projectid} Not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       f"Project Tag {proj.tagid} Not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    
    if not isAdmin and not isProjMember:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'archived' and not isAdmin:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       "Not Authorized (Project archived)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       "Not Authorized (Project unpublished)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if project is published, user must be admin or project member
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE_LIST'), 
                                       "Not Authorized (not Project member)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # generate a list of the (long path) files in the given directory:
    upload_path = config.get_base_path() / 'uploads' / tag.text / '*' 
    result = []
    result.extend(glob.glob(str(upload_path)))
    
    ret = []
    for longPath in result:
        if os.path.isfile(longPath):
            fileSize = os.path.getsize(longPath)
            
            parts = longPath.split('/')
            count = len(parts)
            filename = parts[count-1]
    
            version = 0
            checked_userid = None
            checked_date = None
            modifiable = False
            #
            projFileDB: ProjectFileDB = await crud.get_projectfile_by_filename(filename, proj.projectid)
            # log.info( f"get_project_projectfiles: projFileDB.pfid is {projFileDB.pfid}")
            if projFileDB:
                modifiable = projFileDB.modifiable
                version = projFileDB.version
                checked_userid = projFileDB.checked_userid
                checked_date   = projFileDB.checked_date
                if checked_date:
                    # fix date to be local time:
                    checked_date = convertDateToLocal( checked_date )
            else:
                log.info(f"get_project_projectfiles: untracked file '{filename}' for project '{proj.name}'")
                    
            # returns mimeObject:
            mo = mimelib.url(longPath)
        
            # link = '/static/uploads/' + tag.text + '/' + filename
            link = '/upload/projectFile/' + str(proj.projectid) + '/' + filename
        
            fdesc = {
                "filename": filename,
                "pfid": projFileDB.pfid,
                "projectid": proj.projectid,
                "type": mo.file_type,
                "link": link,
                "size": fileSize,
                "modifiable": modifiable,
                "version": version,
                "checked_userid": checked_userid,
                "checked_date": checked_date
            }
        
            ret.append( fdesc )
        
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_PROJECT_FILE_LIST'), 
                                   f"Project '{proj.name}'" )
        
    return ret


# ----------------------------------------------------------------------------------------------
@router.get("/projectFile/{projectid}/{filename}", response_class=FileResponse)
async def get_projectfile(projectid: int, 
                          filename: str,
                          current_user: UserInDB = Depends(get_current_active_user)):
    
    proj, tag = await crud.get_project_and_tag(projectid)
    # proj = await crud.get_project( projectid )
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                       f"Project {projectid} Not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # tag = await crud.get_tag( proj.tagid )
    if tag is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                       f"Project Tag {proj.tagid} Not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    
    if not isAdmin and not isProjMember:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'archived':
        if not isAdmin:
            await crud.rememberUserAction( current_user.userid, 
                                           UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                           "Not Authorized (Project Archived)" )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")

    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                       "Not Authorized (Project unpublished)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if project is published, user must be admin or project member
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT_FILE'), 
                                       "Not Authorized (not Project member)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # finally...
    upload_path = config.get_base_path() / 'uploads' / tag.text / filename 
    
    if os.path.isfile(upload_path):
        # the file exists, so we deliver it after recording we did so:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('NORMAL'),
                                       UserAction.index('GET_PROJECT_FILE'), 
                                       f"Project '{proj.name}', file {upload_path}" )
        return upload_path
    else:
        # the file is missing! oh nos!
        upload_path = config.get_base_path() / 'static' / 'missingOrArchivedFile.jpg'
        # the file does not exist, so we deliver the missing file image after recording we did so:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('GET_PROJECT_FILE'), 
                                       f"Project '{proj.name}', file {upload_path} was missing, gave missing file image" )
        return upload_path


# ----------------------------------------------------------------------------------------------
# Note: projectid's type is validated as greater than 0  
@router.put("/checkout/{pfid}", response_class=FileResponse)
async def checkout_projectfile(pfid: int, 
                               current_user: UserInDB = Depends(get_current_active_user)):
    
    projFile: ProjectFileDB = await crud.get_projectfile(pfid)
    if projFile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found")
    
    proj, tag = await crud.get_project_and_tag(projFile.projectid)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    if tag is None:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    isModifiable = projFile.modifiable
    
    if not isAdmin and not isProjMember or not isModifiable:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'archived':
        if not isAdmin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")

    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if project is published, user must be admin or project member
    if proj.status == 'published' and (not isAdmin and not isProjMember):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # finally...
    upload_path = config.get_base_path() / 'uploads' / tag.text / projFile.filename 
    
    if os.path.isfile(upload_path):
        # update the projectfile to reflect it is checked out:
        projFile.checked_userid = current_user.userid
        projFile.checked_date = datetime.now() 
        ret = await crud.put_projectfile( projFile )
        if ret != projFile.pfid:
            log.info("checkout_projectfile: almost worked!!!")
        #
        return upload_path
    else:
        # the file is missing! oh nos!
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project File not found")


# ----------------------------------------------------------------------------------------------
# Note: projectid's type is validated as greater than 0  
@router.put("/checkcancel/{pfid}", status_code=200)
async def checkcancel_projectfile(pfid: int, 
                               current_user: UserInDB = Depends(get_current_active_user)):
    
    projFile: ProjectFileDB = await crud.get_projectfile(pfid)
    if projFile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found")
    
    proj, tag = await crud.get_project_and_tag(projFile.projectid)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    if tag is None:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    isAdmin = user_has_role(current_user,"admin")
    # isProjMember = user_has_role(current_user, tag.text)
    isChecker    = projFile.checked_userid == current_user.userid
    
    if not isAdmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if proj.status == 'archived':
        if not isAdmin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")

    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if project is published, user must be admin or project member that checked out file
    if proj.status == 'published' and (not isAdmin and not isChecker):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    if not projFile.modifiable:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # update the projectfile to reflect it is no longer checked out:
    projFile.checked_userid = None
    projFile.checked_date = None 
    return await crud.put_projectfile( projFile )
    
# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/checkin/{pfid}", status_code=200)
async def checkin_projectfile(pfid: int, 
                              file: UploadFile = File(...), 
                              current_user: UserInDB = Depends(get_current_active_user)):
    
    log.info(f"checkin_projectfile: got pfid {pfid}")
    
    projFile: ProjectFileDB = await crud.get_projectfile(pfid)
    if projFile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found")
    
    proj, tag = await crud.get_project_and_tag(projFile.projectid)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    if proj.status == 'archived':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived projects cannot receive checkins")
        
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    if not projFile.modifiable:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    isAdmin = user_has_role(current_user,"admin")
    isProjMember = user_has_role(current_user, tag.text)
    isChecker    = projFile.checked_userid == current_user.userid
    
    log.info( f"checkin_projectfile: isAdmin is {isAdmin}, isProjMember is {isProjMember}, is checker {isChecker}, checked_userid is {projFile.checked_userid}")
    
    # Note: if a person is removed from a project and they have checked out files, they cannot check them in!
    # only admins and project members continue from here:
    if not isAdmin and not isProjMember:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not Authorized to upload {tag.text} files") 
    
    # only allow admins and project owner if project is unpublished:
    if proj.status == 'unpublished' and (not isAdmin and not current_user.userid == proj.userid):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized (Project unpublished)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # if is published, only an admin or the checker-outer can check the file in:
    if proj.status == 'published' and (not isAdmin and not isChecker):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       "Not Authorized (not Project member who checked out file)" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized")
    
    # force original filename of original uploaded file:
    if file.filename != projFile.filename:
        log.info(f"checkin_projectfile: uploaded filename differs ({file.filename}), using original filename ({projFile.filename})")
        file.filename = projFile.filename
    
    log.info(f"checkin_projectfile: about to try...")
    
    upload_path = config.get_base_path() / 'uploads' / tag.text / file.filename
    try:
        #
        log.info(f"checkin_projectfile: attempting {upload_path}")
        #
        async with aiofiles.open(upload_path, 'wb') as f:
            log.info(f"checkin_projectfile: file opened for writing...")
            CHUNK_SIZE = 1024*1024
            while contents := await file.read(CHUNK_SIZE):
                await f.write(contents)
                
    except Exception:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_FILE_UPLOAD'), 
                                       f"Error checking in {file.filename}" )
        return {"message": "There was an error checking in the file"}
    finally:
        await file.close()

    projFile.version += 1
    projFile.checked_userid = None
    projFile.checked_date = None 
    ret = await crud.put_projectfile( projFile )
    if ret != projFile.pfid:
        return {"message": f"Near success checked in {tag.text} {file.filename}, final put failed!"}

    
    return {"message": f"Successfully checked in {tag.text} {file.filename}"}


# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{pfid}", status_code=200)
async def delete_projectfile(pfid: int = Path(..., gt=0), 
                             current_user: UserInDB = Depends(get_current_active_user)):
    
    log.info(f"delete_projectfile: got pfid {pfid}")
    
    projFile: ProjectFileDB = await crud.get_projectfile(pfid)
    if projFile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project file not found")
    
    proj, tag = await crud.get_project_and_tag(projFile.projectid)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    if proj.status == 'archived':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived projects cannot be modified")
        
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    if projFile.checked_userid != None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project file is checked out; cancel check out or check in the file first")

    isAdmin = user_has_role(current_user,"admin")
    isProjOwner = user_has_role(current_user, tag.text) and proj.userid == current_user.userid
    
    log.info( f"delete_projectfile: isAdmin is {isAdmin}, isProjOwner is {isProjOwner}")
    
    # only admins and project owners continue from here:
    if not isAdmin and not isProjOwner:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_FILE_DELETE'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not Authorized to delete {tag.text} files") 
    
    await crud.delete_projectfile(pfid)
    
    log.info( f"delete_projectfile: deleted database record...")

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('DELETE_FILE'), 
                                   f"File {pfid}, {projFile.filename}" )
    
    # make sure file on disk exists before deleting it:
    upload_path = config.get_base_path() / 'uploads' / tag.text / projFile.filename
    if os.path.isfile(upload_path):
        os.remove(upload_path)
        log.info( f"delete_projectfile: deleted file {projFile.filename}")
    else:
        log.info( f"delete_projectfile: file {projFile.filename} did not exist to delete!")
    
    return {"message": "success" }
