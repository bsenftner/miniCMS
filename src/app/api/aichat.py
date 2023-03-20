# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for AI Chat posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, AiChatDB, AiChatCreate, AiChatCreateResponse, ProjectDB, TagDB, basicTextPayload

from typing import List

from app.config import log, get_settings
import json

router = APIRouter()

import openai
openai.api_key = get_settings().OPENAI_API_KEY

# ----------------------------------------------------------------------------------------------
# declare a POST endpoint on the root 
@router.post("/", response_model=AiChatCreateResponse, status_code=201)
async def create_aiChatExchange(payload: AiChatCreate, 
                                current_user: UserInDB = Depends(get_current_active_user)) -> AiChatCreateResponse:
    
    proj: ProjectDB = await crud.get_project(payload.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_AICHAT'), 
                                       f"Project {payload.projectid}, not found" )
        raise HTTPException(status_code=404, detail="AIChat Project not found")
        
    tag: TagDB = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_POST_NEW_AICHAT'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AIChat Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_AICHAT'), 
                                       f"Project {proj.projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create AI Chats for project.")
        
    # MODEL = "gpt-3.5-turbo"
    MODEL = "text-davinci-003"
    prePrompt = '''You are a highly knowledgable attorney. You only answer truthfully.
    If unsure of an answer, say "I am not sure". If you do not have an answer, say "I do not know".
    When you are sure of your answer, reply as a California lawyer. 
    If the question is about a state other than California, or another country, 
    make sure to explain how other states and countries laws may vary from California.
    Be helpful, explaining options, and if you need more information to help ask for the needed information in a polite manner. 
    
    Client: '''
    #
    finalPrompt = prePrompt
    #
    # add in the user's question:
    finalPrompt += payload.prompt
        
    log.info(f"create_aiChatExchange: finalPrompt '{finalPrompt}'")
    
    aiResponse = openai.Completion.create(model=MODEL, 
                                          prompt=finalPrompt,
                                          temperature=0,
                                          max_tokens=900,
                                          # top_p=1,
                                          # frequency_penalty=0.0,
                                          # presence_penalty=0.0,
                                        )["choices"][0]["text"].strip(" \n")
    #
    payload.reply = aiResponse # ['choices'][0]['text']
    #
    log.info(f"create_aiChatExchange: reply '{payload.reply}'")
    
    aichatid = await crud.post_aiChat(payload, current_user)
    
    log.info(f"create_aiChatExchange: aichatid '{aichatid}'")

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('POST_NEW_AICHAT'), 
                                   f"aichatid {aichatid}" )
    
    return { "aichatid": aichatid }

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.get("/{id}", response_model=AiChatDB)
async def read_aichatExchange(id: int = Path(..., gt=0),
                              current_user: UserInDB = Depends(get_current_active_user)) -> AiChatDB:
    
    aichat = await crud.get_aiChat(id)
    if aichat is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"AIChat {id}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AIChat not found")
    
    proj, tag = await crud.get_project_and_tag(aichat.projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"Project {aichat.projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"Project {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_AICHAT'), 
                                   f"AIChat {aichat.aichatid}" )
     
    return aichat

# ----------------------------------------------------------------------------------------------
# The response_model is a List with a AiChatDB subtype. See import of List top of file. 
# Returns a list of the projects the user has access.
@router.get("/project/{projectid}", response_model=List[AiChatDB])
async def read_all_project_aichats(projectid: int = Path(..., gt=0),
                                   current_user: UserInDB = Depends(get_current_active_user)) -> List[AiChatDB]:
    
    proj, tag = await crud.get_project_and_tag(projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATLIST'), 
                                       f"Project {projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    #
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHATLIST'), 
                                       f"Project {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHATLIST'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    # get all the ai chats for this project:
    aichatsList = await crud.get_all_project_aiChats(projectid)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_AICHATLIST'), 
                                   f"AIChat for Project {projectid}, {proj.title}" )
    
    return aichatsList

# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
@router.put("/{aichatid}", response_model=int)
async def update_aiChatExchange(payload: basicTextPayload,       # a new question
                                aichatid: int = Path(..., gt=0), # the aichatid
                                current_user: UserInDB = Depends(get_current_active_user)) -> int:

    aichat = await crud.get_aiChat(aichatid)
    if aichat is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHAT'), 
                                       f"AIChat {id} not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AIChat not found")
    
    proj: ProjectDB = await crud.get_project(aichat.projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHAT'), 
                                       f"Project {aichat.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_UPDATE_AICHAT'), 
                                       f"Project Tag {proj.tagid}, not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
        
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_UPDATE_AICHAT'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    
    MODEL = "text-davinci-003"
    newPrompt = aichat.prompt + " \n" + aichat.reply + "\n" + payload.text
    
    log.info(f"update_aiChatExchange: newPrompt '{newPrompt}'")
    
    aiResponse = openai.Completion.create(model=MODEL, 
                                          prompt=newPrompt,
                                          temperature=0,
                                          max_tokens=900,
                                          # top_p=1,
                                          # frequency_penalty=0.0,
                                          # presence_penalty=0.0,
                                        )["choices"][0]["text"].strip(" \n")
    
    aichat.prompt = aichat.prompt + "<br><br>" + aichat.reply + "<br><br>" + payload.text
    
    aichat.reply = aiResponse 
    
    log.info(f"update_aiChatExchange: reply '{aichat.reply}'")
    
    retVal = await crud.put_aichat( aichat )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_AICHAT'), 
                                   f"aiChat {retVal} updated" )
    
    return retVal
