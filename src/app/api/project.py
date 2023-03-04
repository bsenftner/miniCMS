# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for project posts, handling the CRUD operations with the db 
#
import os
import glob

from fastapi import APIRouter, HTTPException, Path, Depends, status

from app import config
from app.api import crud
from app.api.utils import zipFileList
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.memo import delete_memo
from app.api.upload import get_project_projectfiles
from app.api.models import UserInDB, basicTextPayload, ProjectRequest, ProjectUpdate, ProjectSchema, ProjectDB, TagDB, MemoSchema

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", status_code=201)
async def create_project(payload: ProjectRequest, 
                         current_user: UserInDB = Depends(get_current_active_user)):
    
    if not user_has_role(current_user, "admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to create Projects")
    
    # project tag must be all letters or numbers, no spaces or puncuation 
    # (going to be used as directory name as well as an access role name)
    if payload.tag.isalnum() is False:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                       f"Bad Project Tag '{payload.tag}'" )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                            detail="Bad Project Tag, only use letters and numbers in Project Tags.")
    
    proj = await crud.get_project_by_name( payload.name )
    if proj is not None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                       f"Project name taken '{payload.name}'" )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Project with this name already exists.")
    
    # a tag with the project name needs to also exist, so verify a tag with the requested project name does not exist yet:
    tag = await crud.get_tag_by_name( payload.tag )
    if tag is not None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                       f"Project Tag taken '{payload.tag}'" )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Tag with this name already exists.")
   
    
    log.info(f"create_project: verified Tag '{payload.tag}' does not exist...")
            
    # good, we can create the project AFTER we create a tag with the project tag:
    tagPayload = basicTextPayload( text=payload.tag )
    tagid = await crud.post_tag( tagPayload )
    if tagid is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                       f"Project Tag failed '{payload.tag}'" )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dependant data creation failure.")

    log.info(f"create_project: created Tag '{payload.tag}'")
    
    # projects all receive their own upload directory with the name of the tag text
    proj_upload_path = config.get_base_path() / 'uploads' / payload.tag
    if not os.path.exists(proj_upload_path):
        log.info(f"create_project: attempting to create dir '{proj_upload_path}'")
        try:
            os.makedirs(proj_upload_path, exist_ok = True)
        except OSError as error:
            log.info(f"create_project: failed creating project upload dir '{proj_upload_path}', {error}")
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('SITEBUG'),
                                           UserAction.index('FAILED_POST_NEW_PROJECT'), 
                                           f"Failed creating project upload dir '{proj_upload_path}', {error}" )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dependant data creation failure.")
   
    log.info(f"create_project: created upload dir")
    
    projPayload = ProjectSchema(name=payload.name,
                                text=payload.text,
                                userid=current_user.userid,
                                username=current_user.username,
                                status="unpublished",
                                tagid=tagid)
    projectid = await crud.post_project(projPayload)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('POST_NEW_PROJECT'), 
                                   f"Project '{payload.name}'" )
    
    return { "projectid": projectid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=ProjectDB)
async def read_project(id: int = Path(..., gt=0),
                       current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
    
    # proj, tag = await crud.get_project_and_tag(id)
    proj: ProjectDB = await crud.get_project(id)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"Project {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"Project {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"Project {id}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_PROJECT'), 
                                   f"project {id}, '{proj.name}'" )
    return proj

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a ProjectDB subtype. See import of List top of file. 
# Returns a list of the projects the user has access.
@router.get("/", response_model=List[ProjectDB])
async def read_all_projects(current_user: UserInDB = Depends(get_current_active_user)) -> List[ProjectDB]:
    
    # get all the projects this user has access:
    projList = await crud.get_all_projects(current_user)
            
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_ALL_OWN_PROJECTS'), "" )
    
    return projList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{id}", response_model=int)
async def update_project(payload: ProjectUpdate, 
                         id: int = Path(..., gt=0), 
                         current_user: UserInDB = Depends(get_current_active_user)) -> int:

    proj: ProjectDB = await crud.get_project(id)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_PROJECT'), 
                                       f"Project {id}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_PROJECT'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
        
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_UPDATE_PROJECT'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")

    putPayload = ProjectSchema(
        name=payload.name, 
        text=payload.text, 
        userid=proj.userid,             # retaining original author
        username=proj.username,
        status=payload.status,
        tagid=proj.tagid                # do not allow tagid to change
    )
    projectid = await crud.put_project(id, putPayload)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_MEMO'), 
                                   f"Project {projectid}, '{payload.name}'" )
    
    return projectid

# ----------------------------------------------------------------------------------------------
async def remove_tag_from_users( tag: TagDB ):
    errorCount = 0
    # get list of all project users and remove their project role   
    userList = await crud.get_all_UserDBs_by_role( tag.text )
    for u in userList:
        # from here till the line break is removing 'tag.text' from roles: 
        role_list = u.roles.split()
        u.roles = ''
        first = True
        for role in role_list:
            if role != tag.text:
                if not first:
                    u.roles += ' '
                u.roles += role
            first = False
        # update user in the database: 
        id = await crud.put_user( u.userid, u )
        if id != u.userid:
            errorCount += 1
    return errorCount
                
# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=ProjectDB)
async def delete_project(id: int = Path(..., gt=0), 
                         current_user: UserInDB = Depends(get_current_active_user)) -> ProjectDB:
    
    if not user_has_role(current_user,"admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to delete Projects")
    
    if id==1:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       f"Project {id} cannot be deleted, it's site settings" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cannot delete Project id=1, site settings")
    
    project: ProjectDB = await crud.get_project(id)
    if not project:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       f"Project {id} Not Found" )
        raise HTTPException(status_code=404, detail="Project not found")
    
    tag: TagDB = await crud.get_tag( project.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       f"Project Tag {project.tagid} Not Found" )
        raise HTTPException(status_code=404, detail="Project Tag not found")
    
    # generate a list of the (long path) uploaded files in this project's upload directory:
    upload_path = config.get_base_path() / 'uploads' / tag.text / '*' 
    uploaded_files = []
    uploaded_files.extend(glob.glob(str(upload_path)))
    
    # the uploaded_files list and this list should describe the same files:
    projFileList = await crud.get_project_projectfiles( project.projectid )
    
    # generate a list of the memos in this project:
    projMemoList = await crud.get_all_project_memos( current_user, project.projectid )
    
    if len(uploaded_files) == 0 and len(projFileList) == 0 and len(projMemoList) == 0:
        # if any users are members, remove them from the project:
        errorCount = await remove_tag_from_users( tag )
        if errorCount > 0:
            log.info( f"delete_project: remove_tag_from_users reports {errorCount} errors" )
        # this is a project with no memos and no uploaded files, just delete it:
        await crud.delete_project(id)
        # its upload directory is empty, so delete that too:
        upload_dir = config.get_base_path() / 'uploads' / tag.text
        os.rmdir(upload_dir)
        #
        # remember who, what, when:
        await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('DELETE_PROJECT'), 
                                   f"Project {id}, '{project.name}' had no memos or files, now gone." )
        return project
    
    checked_files = 0
    for pf in projFileList:
        if pf.checked_userid:
            checked_files += 1
    if checked_files > 0:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       f"Project {id}, '{project.name}'  cannot be deleted due to checked out files" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail=f"Project {id}, '{project.name}'  cannot be deleted due to checked out files")
    
    # make sure not already archived:
    if project.status == 'archived':
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('FAILED_DELETE_PROJECT'), 
                                       f"Project '{project.name}' already archived" )
        raise HTTPException(status_code=412, detail=f"Project '{project.name}' already archived")    
        return project
    
    # this project has at least one memo or uploaded file, so archive it:
    
    # if any users are members, remove them from the project:
    errorCount = await remove_tag_from_users( tag )
    if errorCount > 0:
        log.info( f"delete_project: remove_tag_from_users reports {errorCount} errors" )
            
    # archive any files:
    if len(uploaded_files) > 0:
        # path to zip file that will hold the archive:
        zip_archive_path = config.get_base_path() / 'uploads' / tag.text / 'project_' + tag.text + 'archive.zip'
        # create archive
        zipFileList( uploaded_files, zip_archive_path )
        # delete the files: 
        for f in uploaded_files:
            try:
                os.remove(f)
            except OSError as error:
                log.info(f"delete_project: error {error}")
                log.info(f"File path {f} cannot be removed")
                
    # at this location we:
    # 1) get all memos associated with this project 
    # 2) delete them one by one (which also deletes their comments)
    # 3) finally delete the project itself 
    #
    for memo in projMemoList:
        # set each memo as 'archived'
        pm = MemoSchema( title=memo.title,
                         text=memo.text,
                         status='archived',
                         tags=memo.tags,
                         access=memo.access,
                         userid=memo.userid,
                         username=memo.username,
                         projectid=memo.projectid )
        await crud.put_memo( memo.memoid, current_user, pm )
    #
    # finally mark the project as archived:
    ps = ProjectSchema( name=project.name, 
                        text=project.text,
                        userid=project.userid,
                        username=project.username,
                        status='archived',
                        tagid=project.tagid)
    await crud.put_project( project.projectid, ps)
    
    # todo:
    # when searching by tag is implemented, search for anything with the project's tag,
    # if none exist anymore, delete the tag too. 

    # remember who, what, when:
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('DELETE_PROJECT'), 
                                   f"Project {id}, '{project.name}' has been archived" )
        
    return project
