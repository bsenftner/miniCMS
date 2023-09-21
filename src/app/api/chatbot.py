# ------------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for AI Chat Role posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from typing import List
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, ChatbotDB, ChatbotCreate, ChatbotResponse
from app.api.models import ProjectDB, TagDB, ChatbotUpdate

from app.config import log, get_settings

# ---------------------------------------------------------------------------------------

router = APIRouter()

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=ChatbotResponse, status_code=201)
async def create_aiChatRole(payload: ChatbotCreate, 
                            current_user: UserInDB = Depends(get_current_active_user)) -> ChatbotResponse:
    
    proj, tag, cbetag = await crud.get_project_both_tags(payload.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_AICHATROLE'), 
                                       f"Project {payload.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Chatbot Project not found")
        
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_AICHATROLE'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Chatbot Project Tag not found")
    
    if not cbetag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_AICHATROLE'), 
                                       f"Project CBE-Tag {proj.cbetagid}, not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Chatbot Project CBE-Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if weAreAllowed:
        if not user_has_role(current_user,cbetag.text):
            weAreAllowed = False
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_AICHATROLE'), 
                                       f"Project {proj.projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create chatbots for project.")
        
    
    if payload.model=="text-davinci-003":
        pass 
    elif payload.model=="gpt-3.5-turbo" or payload.model=="gpt-4" :
        pass
    else:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_AICHATROLE'), 
                                       f"Unknown or unsupported model '{payload.model}'" )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail=f"Unknown or unsupported model '{payload.model}'")
        
    # first create a db entry for this new aichat 
    chatbotid = await crud.post_Chatbot(payload, current_user)
    #
    log.info(f"create_aiChatRole: chatbotid '{chatbotid}'")
    #
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('POST_NEW_AICHATROLE'), 
                                   f"chatbotid {chatbotid}" )
    
    return { "chatbotid": chatbotid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=ChatbotDB)
async def read_aiChatRole(id: int = Path(..., gt=0),
                          current_user: UserInDB = Depends(get_current_active_user)) -> ChatbotDB:
    
    aiChatRole = await crud.get_Chatbot(id)
    if aiChatRole is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATROLE'), 
                                       f"AIChatRole {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AIChatRole not found")
    
    proj, tag = await crud.get_project_and_tag(aiChatRole.projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATROLE'), 
                                       f"Project {aiChatRole.projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATROLE'), 
                                       f"Project {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHATROLE'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
        
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_AICHATROLE'), 
                                   f"AIChatRole {aiChatRole.chatbotid}" )
    
    return aiChatRole

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a ChatbotDB subtype. See import of List top of file. 
# Returns a list of the projects the user has access.
@router.get("/project/{projectid}", response_model=List[ChatbotDB])
async def read_all_project_aiChatRoles(projectid: int = Path(..., gt=0),
                                       current_user: UserInDB = Depends(get_current_active_user)) -> List[ChatbotDB]:
    
    proj, tag = await crud.get_project_and_tag(projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATROLELIST'), 
                                       f"Project {projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATROLELIST'), 
                                       f"Project {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHATROLELIST'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    # get all the ai chat roles for this project:
    aiChatRolesList = await crud.get_all_project_Chatbots(projectid)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_AICHATROLELIST'), 
                                   f"AIChatRole for Project {projectid}, {proj.title}" )
    
    return aiChatRolesList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{chatbotid}", response_model=ChatbotResponse)
async def update_aiChatRole(payload: ChatbotUpdate,       # potentially updated fields
                            chatbotid: int = Path(..., gt=0), # the aiChatRoleId
                            current_user: UserInDB = Depends(get_current_active_user)) -> ChatbotResponse:

    log.info(f"update_aiChatRole: here!")
    
    aiChatRole: ChatbotDB = await crud.get_Chatbot(chatbotid)
    if aiChatRole is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHATROLE'), 
                                       f"AIChatRole {id} not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AIChat not found")
    
    log.info(f"update_aiChatRole: aiChatRole.name         '{aiChatRole.name}'")
    log.info(f"update_aiChatRole: aiChatRole.prePrompt    '{aiChatRole.prePrompt}'")
    log.info(f"update_aiChatRole: aiChatRole.model        '{aiChatRole.model}'")
    log.info(f"update_aiChatRole: aiChatRole.chatbotid '{aiChatRole.chatbotid}'")
    log.info(f"update_aiChatRole: aiChatRole.projectid    '{aiChatRole.projectid}'")
    log.info(f"update_aiChatRole: aiChatRole.userid       '{aiChatRole.userid}'")
    log.info(f"update_aiChatRole: aiChatRole.username     '{aiChatRole.username}'")
    log.info(f"update_aiChatRole: aiChatRole.created_date '{aiChatRole.created_date}'")
    log.info(f"update_aiChatRole: aiChatRole.updated_date '{aiChatRole.updated_date}'")
    
    proj: ProjectDB = await crud.get_project(aiChatRole.projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHATROLE'), 
                                       f"Project {aiChatRole.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHATROLE'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
        
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_UPDATE_AICHATROLE'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
        
    
    log.info(f"update_aiChatRole: here2!")
    
    aiChatRole.name = payload.name
    aiChatRole.prePrompt = payload.prePrompt
    aiChatRole.model = payload.model
    
    
    log.info(f"updated aiChatRole.name         '{aiChatRole.name}'")
    log.info(f"updated aiChatRole.prePrompt    '{aiChatRole.prePrompt}'")
    log.info(f"updated aiChatRole.model        '{aiChatRole.model}'")
    
    #
    # remember this change
    retVal = await crud.put_Chatbot( aiChatRole )
    
    log.info(f"update_aiChatRole: here3!")
    
    await crud.rememberUserAction( aiChatRole.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_AICHATROLE'), 
                                   f"aiChatRole {retVal} updated" )
    
    return { "chatbotid": chatbotid }