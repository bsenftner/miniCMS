# -------------------------------------------------------------------------------------------------
# This file contains the JSON endpoints for AI Chat posts, handling the CRUD operations with the db 
#
from fastapi import APIRouter, HTTPException, Path, Depends, status

from app.api import crud
from typing import List
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import UserInDB, AiChatDB, AiChatCreate, AiChatCreateResponse, ProjectDB, TagDB, basicTextPayload

from app.config import log, get_settings
import json

import asyncio
import openai

# ---------------------------------------------------------------------------------------

router = APIRouter()

openai.api_key = get_settings().OPENAI_API_KEY

# ----------------------------------------------------------------------------------------------
# new OpenAI communication as separate thread
def OpenAI_thread_comm( aichat: AiChatDB ):
    
    log.info(f"OpenAI_thread_comm: prompt '{aichat.prompt}'")
    
    prePrompt = '''You are a bilingual English and Spanish attorney and CA Law Professor. 
    You work for the Gloria Martinez Law Group, a Sacramento Immigration Law firm. 
    You are meeting a potential client whom is seeking law advice. 
    You want them to hire the firm. 
    You only answer truthfully. 
    Let's work out how to help the client in a step by step way so we are sure 
    to have the right answer, the client understands, and they hire us.
    If multiple options exist for the client, explain each option. 
    If you do not have an answer, say "I do not know".
    
    '''
    
    aiResponse = None
    if aichat.model=="text-davinci-003":        
        aiResponse = openai.Completion.create(model=aichat.model, 
                                              prompt= prePrompt + " \n" + aichat.prompt,
                                              temperature=0,
                                              max_tokens=900,
                                              top_p=1,
                                              frequency_penalty=0.0,
                                              presence_penalty=0.0,
                                        )["choices"][0]["text"].strip(" \n")
    
    elif aichat.model=="gpt-3.5-turbo" or aichat.model=="gpt-4":
        aiResponse = openai.ChatCompletion.create( model=aichat.model,
                                                   messages=[ {"role": "system", "content": prePrompt },
                                                              {"role": "user", "content": aichat.prompt } ],
                                                   temperature=0,
                                                   max_tokens=900,
                                                   top_p=1,
                                                   frequency_penalty=0.0,
                                                   presence_penalty=0.0,
                                                )['choices'][0]['message']['content']
    
    aichat.reply = aiResponse 
    
    log.info(f"OpenAI_thread_comm: reply '{aichat.reply}'")
    
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
    
    if payload.model=="text-davinci-003":
        pass 
    elif payload.model=="gpt-3.5-turbo" or payload.model=="gpt-4" :
        pass
    else:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_POST_NEW_AICHAT'), 
                                       f"Unknown or unsupported model '{payload.model}'" )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail=f"Unknown or unsupported model '{payload.model}'")
        
    aichatid = await crud.post_aiChat(payload, current_user)
    #
    log.info(f"create_aiChatExchange: aichatid '{aichatid}'")
    #
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('POST_NEW_AICHAT'), 
                                   f"aichatid {aichatid}" )
    #
    aichat: AiChatDB = await crud.get_aiChat( aichatid )
    
    await asyncio.to_thread(OpenAI_thread_comm, aichat)
    
    retVal = await crud.put_aichat( aichat )
    
    await crud.rememberUserAction( aichat.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_AICHAT'), 
                                   f"aiChat {retVal} updated in thread" )
    
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

'''
aichat.prompt = aichat.prompt + "<br><br>" + aichat.reply + "<br><br>" + payload.text
    
    aichat.reply = '' 
    
    retVal = await crud.put_aichat( aichat ) 
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_AICHAT'), 
                                   f"aiChat {retVal} updated in put" )
    
    # this method (commented out) runs with a coroutine:
    # await fifo_queue.put({ "runner": OpenAI_communication, "param": aichat})
    #
    # this version runs in a separate thead, requiring the following two lines 
    # the other method does in its coroutine
    await asyncio.to_thread(OpenAI_thread_comm, aichat )
'''
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
        

    aichat.prompt = aichat.prompt + "<br><br>" + aichat.reply + "<br><br>" + payload.text
    aichat.reply = ''
    await asyncio.to_thread(OpenAI_thread_comm, aichat )

    
    retVal = await crud.put_aichat( aichat )
    
    await crud.rememberUserAction( aichat.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('UPDATE_AICHAT'), 
                                   f"aiChat {retVal} updated in thread" )
    
    return retVal
