from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from starlette.responses import RedirectResponse

import json

from app import config
from app.api import crud, users
from app.api.models import User, MemoDB, ProjectDB
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

    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "home.html",
        {"request": request, "frags": FRAGS, "access": "public", "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve registration page thru a Jinja2 template:
@router.get("/register", status_code=status.HTTP_201_CREATED, response_class=HTMLResponse)
async def register( request: Request ):

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

    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "login.html",
        {"request": request, "frags": FRAGS, "access": "public", "memos": memoList}, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/profile", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def profilePage( request: Request,  
                       current_user: User = Depends(users.get_current_active_user) ):

    # config.log.info(f"profilePage: here!")
    
    memoList = await crud.get_all_memos(current_user)
    
    # config.log.info(f"profilePage: got the memos...")
    
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
                       current_user: User = Depends(users.get_current_active_user) ):
    
    config.log.info("projectPage: here!!")
     
    proj: ProjectDB = await crud.get_project(projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    weAreAllowed = crud.user_has_project_access( current_user, proj )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, projectid)
    
    # returns list of all project users:
    userList = await crud.get_all_users_by_role( proj.name )
    
    return TEMPLATES.TemplateResponse(
        "project.html",
        { "request": request, 
          "contentPost": proj, 
          "frags": FRAGS, 
          "access": 'private',
          "users": userList,
          "memos": memoList,
        }, 
        # 'access' key is for template left sidebar construction
    )

# ------------------------------------------------------------------------------------------------------------------
# serve project on an editor thru a template:
@router.get("/projectEditor/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def projectEditor( request: Request, 
                         id: int, 
                         current_user: User = Depends(users.get_current_active_user) ):
    
    proj: ProjectDB = await crud.get_project(id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    if proj.userid != current_user.userid and not users.user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to edit other's Projects")
        
    memoList = await crud.get_all_project_memos(current_user, id)
    
    return TEMPLATES.TemplateResponse(
        "projectEditor.html", 
        {"request": request, 
         "contentPost": proj, 
         "frags": FRAGS, 
         "access": 'private', 
         "memos": memoList,
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve project on an editor thru a template:
@router.get("/newProject", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def projectEditor( request: Request, 
                         current_user: User = Depends(users.get_current_active_user) ):
    
    if not users.user_has_role(current_user,"admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to create Projects")
    
    proj = ProjectDB( name='yourProjectName',
                      text='Edit this to describe your project.',\
                      userid=current_user.userid,
                      username=current_user.username,
                      status='unpublished',
                      tagid=0,
                      projectid=0)
        
    memoList = []
    
    return TEMPLATES.TemplateResponse(
        "projectEditor.html", 
        {"request": request, 
         "contentPost": proj, 
         "frags": FRAGS, 
         "access": 'private', 
         "memos": memoList,
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/memoPage/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def memoPage( request: Request, 
                    id: int, 
                    current_user: User = Depends(users.get_current_active_user) ):
    
    memo: MemoDB = await crud.get_memo(id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Memo Project not found")
    
    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo")
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    return TEMPLATES.TemplateResponse(
        "memo.html",
        { "request": request, 
          "contentPost": memo, 
          "parentName": proj.name,
          "frags": FRAGS, 
          "access": 'private',
          "memos": memoList,
        }, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve the requested page thru a Jinja2 template:
@router.get("/publicmemo/{id}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def memoPublic( request: Request, id: int  ):
    
    memo: MemoDB = await crud.get_memo(id)
    if not memo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")

    if 'public' not in memo.access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Memo not publc.")
        
    memoList = await crud.get_all_public_memos()
    
    return TEMPLATES.TemplateResponse(
        "index.html",
        { "request": request, 
          "contentPost": memo, 
          "frags": FRAGS, 
          "access": 'public',
          "memos": memoList 
        }, 
        # 'access' key is for template left sidebar construction
    )
    

# ------------------------------------------------------------------------------------------------------------------
# serve existing memo on an editor thru a template:
@router.get("/memoEditor/{memoid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def editor( request: Request, 
                  memoid: int, 
                  current_user: User = Depends(users.get_current_active_user) ):
    
    memo: MemoDB = await crud.get_memo(memoid)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    
    proj: ProjectDB = await crud.get_project(memo.projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Memo Project not found")

    weAreAllowed = await crud.user_has_memo_access( current_user, memo )
    if not weAreAllowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access memo")
        
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    return TEMPLATES.TemplateResponse(
        "memoEditor.html", 
        {"request": request, 
         "contentPost": memo, 
         "parentName": proj.name,
         "frags": FRAGS, 
         "access": 'private', 
         "memos": memoList,
        }, 
        # 'access' key is for template left sidebar construction
    )
    
# ------------------------------------------------------------------------------------------------------------------
# serve an empty editor page that saves as a memo thru a template:
@router.get("/newProjectMemo/{projectid}", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def editor( request: Request, 
                  projectid: int,
                  current_user: User = Depends(users.get_current_active_user) ):
    
    proj: ProjectDB = await crud.get_project(projectid)
    if not proj:
        raise HTTPException(status_code=404, detail="Memo Project not found")
    
    memo = MemoDB( memoid=0,
                   title='your memo title',
                   text='Edit this to be your memo.',
                   status='unpublished',
                   tags=proj.name,
                   access='staff ',
                   userid=current_user.userid,
                   username=current_user.username,
                   projectid=proj.projectid)
    
    # returns list of project memos this user has access:
    memoList = await crud.get_all_project_memos(current_user, memo.projectid)
    
    return TEMPLATES.TemplateResponse(
        "memoEditor.html", 
        { "request": request, 
          "contentPost": memo, 
          "parentName": proj.name,
          "frags": FRAGS, 
          "access": 'private', 
          "memos": memoList
        }, 
        # 'access' key is for template left sidebar construction
    )
    
    
# ------------------------------------------------------------------------------------------------------------------
# serve a user profile page thru a template:
@router.get("/settings", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def user_settings_page( request: Request, 
                              current_user: User = Depends(users.get_current_active_user) ):
    
    # default info available to the page: 
    page_data = {
        'username': current_user.username,
        'email': current_user.email,
        'roles': current_user.roles,
    }
    
    # list of memo posts:
    memoList = await crud.get_all_memos(current_user)
    
    for m in memoList:
        config.log.info(f"user_settings_page: working with memo.memoid {m.memoid}")
        
    # if an ordinary user get user_page, if admin get admin_page: 
    page = 'user_page.html'
    if users.user_has_role( current_user, "admin"):
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
    
     
 