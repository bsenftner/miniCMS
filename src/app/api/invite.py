# ---------------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for project invite posts, handling the CRUD operations with the db 
#

from fastapi import APIRouter, HTTPException, Path, Depends, status

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role, get_user
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, ProjectInviteCreate, ProjectInviteDB, ProjectInviteUpdate, ProjectInvitePublic

from typing import List

from app.config import log

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", status_code=201)
async def create_proj_invite(payload: ProjectInviteCreate, 
                            current_user: UserInDB = Depends(get_current_active_user)):
    
    log.info(f"create_proj_invite: posting {payload}")
    
    proj, tag = await crud.get_project_and_tag(payload.projectid)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    user = await crud.get_user_by_id( payload.touserid )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    #
    touser = UserInDB(username =user.username, 
                      userid = user.userid, 
                      roles = user.roles, 
                      email = user.email,
                      verify_code = user.verify_code,
                      hashed_password = user.hashed_password) 
    
    log.info(f"create_proj_invite: touser is {touser}")
    log.info(f"create_proj_invite: tag is {tag.text}")
    
    alreadyMember = user_has_role(touser, tag.text)
    if alreadyMember:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already project member")
    
    alreadyInvited = False
    inviteList = await crud.get_user_projInvites( touser )
    
    log.info(f"create_proj_invite: inviteList is {inviteList}")
    
    for invite in inviteList:
        if invite.projectid == payload.projectid:
            alreadyInvited = True
    if alreadyInvited:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already invited to project")
    
    inviteid = await crud.post_projInvite(payload, tag.text, current_user)

    log.info(f"create_proj_invite: returning id {inviteid}")
    
    return { "inviteid": inviteid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=ProjectInvitePublic)
async def read_proj_invite(id: int = Path(..., gt=0),
                          current_user: UserInDB = Depends(get_current_active_user)) -> ProjectInvitePublic:
    
    invite: ProjectInviteDB = await crud.get_projInvite(id)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project invite not found")
    
    # first unverified automatically get denied access:
    weAreAllowed = not user_has_role(current_user, 'unverified')
    if weAreAllowed:
        # next admins automatically get access:
        weAreAllowed = user_has_role(current_user, 'admin')
        if not weAreAllowed:
            # if we're the inviter:
            if invite.byuserid == current_user.userid:
                weAreAllowed = True
            elif invite.touserid == current_user.userid:
                weAreAllowed = True
    #
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project invite.")
    
    # get the project the invite is concerned:
    proj, tag = await crud.get_project_and_tag(id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    publicInvite = ProjectInvitePublic( projectname = proj.name,
                                       inviteid = invite.inviteid,
                                       projectid = invite.projectid,
                                       tag = tag.text,
                                       byuserid = invite.byuserid,
                                       touserid = invite.touserid,
                                       status = invite.status )
    
    return publicInvite

# ----------------------------------------------------------------------------------------------
# Returns a list of the invites issued to the current user
# The response_model is a List with a ProjectInviteDB subtype. See import of List top of file. 
@router.get("/", response_model=List[ProjectInvitePublic])
async def read_all_user_invites(current_user: UserInDB = Depends(get_current_active_user)) -> List[ProjectInvitePublic]:
    
    # get all this user's invites:
    inviteList = await crud.get_user_projInvites(current_user)
            
    publicInviteList = []
    for invite in inviteList:
        # get the project the invite is concerned:
        proj, tag = await crud.get_project_and_tag(invite.projectid)
        if proj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {invite.projectid} not found")
        #
        if not tag:
            raise HTTPException(status_code=500, detail=f"Project Tag for Project with id {invite.projectid} not found")
        #
        publicInvite = ProjectInvitePublic( projectname = proj.name,
                                            inviteid = invite.inviteid,
                                            projectid = invite.projectid,
                                            tag = tag.text,
                                            byuserid = invite.byuserid,
                                            touserid = invite.touserid,
                                            status = invite.status )
        publicInviteList.append(publicInvite)
    
    return publicInviteList

# ----------------------------------------------------------------------------------------------
# Returns a list of the invites issued to the specified user
# The response_model is a List with a ProjectInviteDB subtype. See import of List top of file. 
@router.get("/user/{userid}", response_model=List[ProjectInvitePublic])
async def read_all_other_user_invites(userid: int = Path(..., gt=0),
                                     current_user: UserInDB = Depends(get_current_active_user)) -> List[ProjectInvitePublic]:
    
    user = await crud.get_user_by_id( userid )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    log.info(f"read_all_other_user_invites: got user {user}")
    
    # get all this user's invites:
    inviteList = await crud.get_user_projInvites(user)
            
    publicInviteList = []
    for invite in inviteList:
        # get the project the invite is concerned:
        proj, tag = await crud.get_project_and_tag(invite.projectid)
        if proj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {invite.projectid} not found")
        #
        if not tag:
            raise HTTPException(status_code=500, detail=f"Project Tag for Project with id {invite.projectid} not found")
        #
        publicInvite = ProjectInvitePublic( projectname = proj.name,
                                            inviteid = invite.inviteid,
                                            projectid = invite.projectid,
                                            tag = tag.text,
                                            byuserid = invite.byuserid,
                                            touserid = invite.touserid,
                                            status = invite.status )
        publicInviteList.append(publicInvite)
        
    return publicInviteList

# ----------------------------------------------------------------------------------------------
# Returns a list of the invites for the specified project
# The response_model is a List with a ProjectInviteDB subtype. See import of List top of file. 
@router.get("/project/{projectid}", response_model=List[ProjectInvitePublic])
async def read_all_project_invites(projectid: int = Path(..., gt=0),
                                   current_user: UserInDB = Depends(get_current_active_user)) -> List[ProjectInvitePublic]:
    
    log.info(f"read_all_project_invites: got projectid {projectid}")
    
    # get all this user's invites:
    inviteList = await crud.get_project_projInvites( projectid )
            
    publicInviteList = []
    for invite in inviteList:
        # get the project the invite is concerned:
        proj, tag = await crud.get_project_and_tag(invite.projectid)
        if proj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {invite.projectid} not found")
        #
        if not tag:
            raise HTTPException(status_code=500, detail=f"Project Tag for Project with id {invite.projectid} not found")
        #
        publicInvite = ProjectInvitePublic( projectname = proj.name,
                                            inviteid = invite.inviteid,
                                            projectid = invite.projectid,
                                            tag = tag.text,
                                            byuserid = invite.byuserid,
                                            touserid = invite.touserid,
                                            status = invite.status )
        publicInviteList.append(publicInvite)
        
    return publicInviteList


# ----------------------------------------------------------------------------------------------
# update a ProjectInviteDB
# Note: id's type is validated as greater than 0  
@router.put("/{id}")
async def update_proj_invite(payload: ProjectInviteUpdate, 
                             id: int = Path(..., gt=0), 
                             current_user: UserInDB = Depends(get_current_active_user)):
   
    log.info("update_proj_invite: here!!")
    
    if payload.status < 0 or payload.status > 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project invite status not allowed")
    
    invite: ProjectInviteDB = await crud.get_projInvite(id)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project invite not found")
    
    log.info(f'update_proj_invite: got invite {invite}')
    
    cid = current_user.userid
    if not user_has_role(current_user,"admin") and cid!=invite.touserid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to change Project Invite")

    user = await crud.get_user_by_id( invite.touserid )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    #
    touser = UserInDB(username =user.username, 
                      userid = user.userid, 
                      roles = user.roles, 
                      email = user.email,
                      verify_code = user.verify_code,
                      hashed_password = user.hashed_password)
    
    log.info(f'update_proj_invite: got touser {touser}')
    
    if user_has_role( touser, invite.tag ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already project member")
    
    log.info(f'update_proj_invite: doing put...')
    
    inviteid = await crud.put_projInvite(id, payload)
    if inviteid != invite.inviteid:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")
    
    log.info(f'update_proj_invite: back from put')
    
    if payload.status == 1:
        # make touser a member of the project:
        old_roles = touser.roles
        touser.roles += " " + invite.tag
        #
        log.info(f'update_proj_invite: updating user...')
        #
        id = await crud.put_user( touser.userid, touser )
        if id!=touser.userid:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    
    log.info(f'update_proj_invite: preparing to return...')
    
    return inviteid

# ----------------------------------------------------------------------------------------------
# delete a ProjectInviteDB, with protection: only works for touser, byuser and admins
# Note: id's type is validated as greater than 0  
@router.delete("/{id}", response_model=ProjectInviteDB)
async def delete_proj_invite(id: int = Path(..., gt=0), 
                             current_user: UserInDB = Depends(get_current_active_user)) -> ProjectInviteDB:
    
    invite: ProjectInviteDB = await crud.get_projInvite(id)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project Invite not found")

    cid = current_user.userid
    if cid != invite.touserid and cid != invite.byuserid and not user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to delete other's Project Invites")
        
    await crud.delete_projInvite(id)

    return invite
