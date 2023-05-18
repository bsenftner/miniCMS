from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import os
from datetime import datetime
# from dateutil import tz

from starlette.responses import RedirectResponse

import json

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
from app.api.models import User, MemoDB, ProjectDB, NoteDB, AiChatDB
from app.api.utils import convertDateToLocal
# from app.send_email import send_email_async

# page_frag.py contains common page fragments, like .header & .footer.
# This is passed to page templates for repeated use of common html fragments: 
from app.page_frags import FRAGS 


TEMPLATES = Jinja2Templates(directory=str(config.get_base_path() / "templates"))


# define a router for the html returning endpoints: 
router = APIRouter()


   
# ------------------------------------------------------------------------------------------------------------------
# added to get favicon served:
favicon_path = config.get_base_path() / 'favicon.ico'
@router.get("/favicon.ico", status_code=200, include_in_schema=False) 
def favicon():
    """
    Favicon.ico GET
    """
    # print(f"favicon_path is {favicon_path}")
    return FileResponse(favicon_path)


# ------------------------------------------------------------------------------------------------------------------
# serve homepage thru a Jinja2 template:
@router.get("/", status_code=200, response_class=HTMLResponse)
async def root( request: Request ):

    site_config: NoteDB = await crud.get_note(1) # site_config has id 1
    if site_config:
        site_config.data = json.loads(site_config.data)
        
    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "home.html",
        {"request": request, 
         "frags": FRAGS, 
         "regers": site_config.data['public_registration'],
         "access": "public", 
         "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve registration page thru a Jinja2 template:
@router.get("/register", status_code=status.HTTP_201_CREATED, response_class=HTMLResponse)
async def register( request: Request ):
    
    site_config: NoteDB = await crud.get_note(1) # site_config has id 1
    if site_config:
        site_config.data = json.loads(site_config.data)
        # config.log.info(f"register: site_config.data is {site_config.data}")
        if site_config.data['public_registration'] == False:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                detail="Public registration is unauthorized")
    
    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "register.html",
        {"request": request, "frags": FRAGS, "access": "public", "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve login page thru a Jinja2 template:
@router.get("/login", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def login( request: Request ):

    site_config: NoteDB = await crud.get_note(1) # site_config has id 1
    if site_config:
        site_config.data = json.loads(site_config.data)
        
    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "login.html",
        {"request": request, 
         "frags": FRAGS, 
         "regers": site_config.data['public_registration'],
         "access": "public", 
         "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/profile", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def profilePage( request: Request,  
                       current_user: User = Depends(get_current_active_user) ):
    
    config.log.info(f"profilePage: current_user: {current_user}")

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_USER_PROFILE'), "" )
    
    memoList = await crud.get_all_memos(current_user)
    
    return TEMPLATES.TemplateResponse(
        "profile.html",
        { "request": request, 
          "contentPost": current_user, 
          "frags": FRAGS, 
          "access": 'private',
          "memos": memoList }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/projectPage/{projectid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def projectPage( request: Request, projectid: int, 
                       current_user: User = Depends(get_current_active_user) ):
     
    proj, tag = await crud.get_project_and_tag(projectid) 
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"ProjectPage {projectid}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"ProjectPage {projectid}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_PROJECT'), 
                                       f"ProjectPage {projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    # projects all receive their own upload directory with the name of the tag text,
    # but the developer may delete project dirs willy-nilly, let's verify that dir exists:
    proj_upload_path = config.get_base_path() / 'uploads' / tag.text
    if not os.path.exists(proj_upload_path):
        config.log.info(f"projectPage: attempting to create dir '{proj_upload_path}'")
        try:
            os.makedirs(proj_upload_path, exist_ok = True)
        except OSError as error:
            config.log.info(f"projectPage: failed creating project upload dir '{proj_upload_path}', {error}")
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('SITEBUG'),
                                           UserAction.index('FAILED_GET_PROJECT'), 
                                           f"Failed creating project upload dir '{proj_upload_path}', {error}" )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dependant data creation failure.")
        
    if (proj.status == 'archived'):
        proj.name += ' (archived)'
        proj.text = '<h3>(Embedded files do not display in archived projects)</h3>' + proj.text 
        
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
     
    # returns list of all project users:
    userList = await crud.get_all_users_by_role( proj.name )
    
    # returns list of project memos this user has access:
    # note: if project is unpublished the title is altered to have "(unpublished)" at the end
    memoList = await crud.get_all_project_memos(current_user, projectid)
    
    # fix date to be local time:
    local_dt = convertDateToLocal( proj.created_date )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_PROJECT'), 
                                   f"projectPage {projectid}, '{proj.name}'" )
    
    return TEMPLATES.TemplateResponse(
        "project.html",
        { "request": request, 
          "contentPost": proj, 
          "projectTag": tag.text,
          "projectCreated": local_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'private',
          "users": userList,
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )

# ------------------------------------------------------------------------------------------------------------------
# serve project on an editor thru a template:
@router.get("/projectEditor/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def projectEditor( request: Request, 
                         id: int, 
                         current_user: User = Depends(get_current_active_user) ):
    
    proj, tag = await crud.get_project_and_tag(id)
    # proj: ProjectDB = await crud.get_project(id)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_PROJECT'), 
                                       f"projectEditor {id}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")

    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_PROJECT'), 
                                       f"ProjectPage {id}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_EDIT_PROJECT'), 
                                       f"ProjectPage {id}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to edit project.")
    
    # projects all receive their own upload directory with the name of the tag text,
    # but the developer may delete project dirs willy-nilly, let's verify that dir exists:
    proj_upload_path = config.get_base_path() / 'uploads' / tag.text
    if not os.path.exists(proj_upload_path):
        config.log.info(f"projectPage: attempting to create dir '{proj_upload_path}'")
        try:
            os.makedirs(proj_upload_path, exist_ok = True)
        except OSError as error:
            config.log.info(f"projectPage: failed creating project upload dir '{proj_upload_path}', {error}")
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('SITEBUG'),
                                           UserAction.index('FAILED_EDIT_PROJECT'), 
                                           f"Failed creating project upload dir '{proj_upload_path}', {error}" )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dependant data creation failure.")
        
    if (proj.status == 'archived'):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_EDIT_PROJECT'), 
                                       f"ProjectPage {id}, '{proj.name}', is archived, cannot be edited" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized, archived project.") 
        
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
        
    memoList = await crud.get_all_project_memos(current_user, id)
    
    local_dt = convertDateToLocal( proj.created_date )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('EDIT_PROJECT'), 
                                   f"projectEditor {id}, '{proj.name}'" )
    
    return TEMPLATES.TemplateResponse(
        "projectEditor.html", 
        { "request": request, 
          "contentPost": proj, 
          "projectTag": tag.text,
          "projectCreated": local_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'private', 
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve project on an editor thru a template:
@router.get("/newProject", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def newProjectEditor( request: Request, 
                            current_user: User = Depends(get_current_active_user) ):
    
    isAdmin = user_has_role(current_user,"admin")
    
    """ allowing non-admins to create projects:
    if not isAdmin:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('NONADMIN_ATTEMPTED_EDIT_NEW_PROJECT'), "" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to create Projects") """
    
    # the app runs in UTC local time:
    created_date = datetime.now()
    local_dt = convertDateToLocal( created_date )
    
    proj = ProjectDB( name='yourProjectName',
                      text='Edit this to describe your project.',\
                      userid=current_user.userid,
                      username=current_user.username,
                      status='unpublished',
                      tagid=0,
                      projectid=0,
                      created_date=created_date)
        
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('EDIT_NEW_PROJECT'), "" )
    
    memoList = []
    
    return TEMPLATES.TemplateResponse(
        "projectEditor.html", 
        {"request": request, 
         "contentPost": proj, 
         "projectTag": "",
         "projectCreated": local_dt.strftime("%c"),
         "frags": FRAGS, 
         "access": 'private', 
         "memos": memoList,
         "userid": current_user.userid,
         "isAdmin": isAdmin,
         "isOwner": True
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/memoPage/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def memoPage( request: Request, 
                    id: int, 
                    current_user: User = Depends(get_current_active_user) ):
    
    memo: MemoDB = await crud.get_memo(id)
    if not memo:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_MEMO'), 
                                       f"memoPage {id}, not found" )
        raise HTTPException(status_code=404, detail="Memo not found")
    
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_MEMO'), 
                                       f"memoPage {id}, Project {memo.projectid} not found" )
        raise HTTPException(status_code=404, detail="Memo Project not found")
    
    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_MEMO'), "Not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_MEMO'), 
                                   f"memoPage {id} '{memo.title}'" )
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    localCreated_dt = convertDateToLocal( memo.created_date )
    localUpdated_dt = convertDateToLocal( memo.updated_date )
    
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
    
    return TEMPLATES.TemplateResponse(
        "memo.html",
        { "request": request, 
          "contentPost": memo, 
          "parentName": proj.name,
          "memoCreated": localCreated_dt.strftime("%c"),
          "memoUpdated": localUpdated_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'private',
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/publicmemo/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def memoPublic( request: Request, id: int  ):
    
    # config.log.info(f"memoPublic: got {id}")
    
    memo: MemoDB = await crud.get_memo(id)
    if not memo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")

    # config.log.info(f"memoPublic: memo.access is {memo.access}")
    
    if 'public' not in memo.access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Memo not publc.")
        
    # config.log.info(f"memoPublic: yep, we are public")
    
    memoList = await crud.get_all_public_memos()
    
    localCreated_dt = convertDateToLocal( memo.created_date )
    localUpdated_dt = convertDateToLocal( memo.updated_date )
    
    return TEMPLATES.TemplateResponse(
        "index.html",
        { "request": request, 
          "contentPost": memo, 
          "memoCreated": localCreated_dt.strftime("%c"),
          "memoUpdated": localUpdated_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'public',
          "memos": memoList 
        }, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve existing memo on an editor thru a template:
@router.get("/memoEditor/{memoid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def memoEditor( request: Request, 
                      memoid: int, 
                      current_user: User = Depends(get_current_active_user) ):
    
    memo: MemoDB = await crud.get_memo(memoid)
    if not memo:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_MEMO'), 
                                       f"requested memo {memoid}, not found" )
        raise HTTPException(status_code=404, detail="Memo not found")
    
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_MEMO'), 
                                       f"requested memo {id}, Project {memo.projectid} not found" )
        raise HTTPException(status_code=404, detail="Memo Project not found")

    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_EDIT_MEMO'), 
                                       f"Memo {memoid}, Not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo")
        
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('EDIT_MEMO'), 
                                   f"memo {memoid} '{memo.title}'" )
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    localCreated_dt = convertDateToLocal( memo.created_date )
    localUpdated_dt = convertDateToLocal( memo.updated_date )
    
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid

    return TEMPLATES.TemplateResponse(
        "memoEditor.html", 
        { "request": request, 
          "contentPost": memo, 
          "memoCreated": localCreated_dt.strftime("%c"),
          "memoUpdated": localUpdated_dt.strftime("%c"),
          "parentName": proj.name,
          "frags": FRAGS, 
          "access": 'private', 
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve an empty editor page that saves as a memo thru a template:
@router.get("/newProjectMemo/{projectid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def newMemoEditor( request: Request, 
                         projectid: int,
                         current_user: User = Depends(get_current_active_user) ):
    
    proj: ProjectDB = await crud.get_project(projectid)
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_NEW_MEMO'), 
                                       f"Project {projectid} not found" )
        raise HTTPException(status_code=404, detail="Memo Project not found")
    
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_EDIT_NEW_MEMO'), 
                                       f"Project Tag {proj.tagid} not found" )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_EDIT_NEW_MEMO'), 
                                       f"ProjectPage {projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")

    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('EDIT_NEW_MEMO'), 
                                   f"for Project '{proj.name}'" )
    
    # the app runs in UTC local time:
    created_date = datetime.now()
    local_dt = convertDateToLocal( created_date )
    
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
    
    memo = MemoDB( memoid=0,
                   title='your memo title',
                   text='Edit this to be your memo.',
                   status='unpublished',
                   tags=tag.text,
                   access='staff',
                   userid=current_user.userid,
                   username=current_user.username,
                   projectid=proj.projectid,
                   created_date=datetime.now(),
                   updated_date=datetime.now())
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    return TEMPLATES.TemplateResponse(
        "memoEditor.html", 
        { "request": request, 
          "contentPost": memo, 
          "parentName": proj.name,
          "parentTag": tag.text,
          "memoCreated": local_dt.strftime("%c"),
          "memoUpdated": local_dt.strftime("%c"),  # new memo, so both are same
          "frags": FRAGS, 
          "access": 'private', 
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/newAiExchange/{projectid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def newAichatPage( request: Request, 
                      projectid: int, 
                      current_user: User = Depends(get_current_active_user) ):
    
    proj, tag = await crud.get_project_and_tag(projectid) 
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"newAichat, project {projectid}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"newAichat, project {projectid}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"newAichat, project {projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('NEW_AICHAT_PAGE'), 
                                   f"newAichat, project {projectid}" )
    
    aichatList = await crud.get_all_project_aiChats(projectid)
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, projectid)
    
     # the app runs in UTC local time:
    created_date = datetime.now()
    localCreated_dt = convertDateToLocal( created_date )
    localUpdated_dt = convertDateToLocal( created_date )
    
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
    
    return TEMPLATES.TemplateResponse(
        "aichat.html",
        { "request": request, 
          "contentPost": { "aichatid":"new", "username":current_user.username, "projectid": projectid }, 
          "aichatList": aichatList,
          "parentName": proj.name,
          "aichatCreated": localCreated_dt.strftime("%c"),
          "aichatUpdated": localUpdated_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'private',
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/aiExchange/{aichatid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def aichatPage( request: Request, 
                      aichatid: int, 
                      current_user: User = Depends(get_current_active_user) ):
    
    aichat: AiChatDB = await crud.get_aiChat(aichatid)
    if not aichat:
        raise HTTPException(status_code=404, detail="AiChat not found")
    
    proj, tag = await crud.get_project_and_tag(aichat.projectid) 
    if not proj:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"aichat, project {aichat.projectid}, not found" )
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"aichat, project {proj.projectid}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_GET_AICHAT'), 
                                       f"aichat, project {proj.projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('NEW_AICHAT_PAGE'), 
                                   f"aichat, project {proj.projectid}, chat {aichat.aichatid}" )
    
    aichatList = await crud.get_all_project_aiChats(proj.projectid)
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, proj.projectid)
    
     # the app runs in UTC local time:
    created_date = aichat.created_date
    updated_date = aichat.updated_date
    localCreated_dt = convertDateToLocal( created_date )
    localUpdated_dt = convertDateToLocal( updated_date )
    
    isAdmin = user_has_role(current_user,"admin")
    isOwner = current_user.userid == proj.userid
    
    return TEMPLATES.TemplateResponse(
        "aichat.html",
        { "request": request, 
          "contentPost": aichat, 
          "aichatList": aichatList,
          "parentName": proj.name,
          "aichatCreated": localCreated_dt.strftime("%c"),
          "aichatUpdated": localUpdated_dt.strftime("%c"),
          "frags": FRAGS, 
          "access": 'private',
          "memos": memoList,
          "userid": current_user.userid,
          "isAdmin": isAdmin,
          "isOwner": isOwner
        }, 
        # 'access' key is for template left sidebar construction
    )
    
    
# ------------------------------------------------------------------------------------------------------------------
# serve a user account settings page thru a template:
@router.get("/settings", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def user_settings_page( request: Request, 
                              current_user: User = Depends(get_current_active_user) ):
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('GET_OWN_SETTINGS_PAGE'), 
                                   "" )
    
    # default info available to the page: 
    page_data = {
        'username': current_user.username,
        'email': current_user.email,
        'roles': current_user.roles,
    }
    
    # list of memo posts:
    memoList = await crud.get_all_memos(current_user)
        
    # if an ordinary user get user_page, if admin get admin_page: 
    page = 'user_page.html'
    if user_has_role( current_user, "admin"):
        page = 'admin_page.html'
        
        # get site_config note to add to the admin page 
        # more items that can be changed:
        site_config = await crud.get_note(1) # site_config has id 1
        if site_config:
            site_config.data = json.loads(site_config.data)
            page_data.update(site_config.data)
       
    return TEMPLATES.TemplateResponse(
        page,
        {"request": request, "data": page_data, "frags": FRAGS, "access": 'private', "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    
     
 