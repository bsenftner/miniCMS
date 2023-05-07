from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware 


from app import config
from app.db import DatabaseMgr, get_database_mgr
from app.api import project, memo, comment, tag, notes, ping, users_htmlpages, video
from app.api import htmlpages, upload, backups, user_action, aichat, invite
from app.config import log

# import sentry_sdk

# ---------------------------------------------------------------------------------------
# generate our "app"
def create_application() -> FastAPI:

    application = FastAPI(title="MiniCMS", openapi_url="/openapi.json")

    origins = ["*"]
    
    # add CORS handling: 
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )
    
    # enable automatic serving of contents of "static" directory: 
    application.mount("/static", StaticFiles(directory=str(config.get_base_path() / "static")), name="static") 

    
    
    # isolate these activities into their own file:
    from app.startup import initialize_database_data
    #
    # setup handler for application start that inits the db connection: 
    @application.on_event("startup")
    async def startup():
        db_mgr: DatabaseMgr = get_database_mgr()
        await db_mgr.get_db().connect()
        await initialize_database_data(application)
    #     
    # setup handler for application shutdown that disconnects the db: 
    @application.on_event("shutdown")
    async def shutdown():
        db_mgr: DatabaseMgr = get_database_mgr()
        await db_mgr.get_db().disconnect()


    # install the ping router into our app:
    application.include_router(ping.router)

    # install the tag router into our app with a prefix & tag too:
    application.include_router(tag.router, prefix="/tag", tags=["tag"])
    
    # install the notes router into our app;
    # note the prefix URL along with the "notes" tag, 
    # the prefix places the routes defined by notes.router after "/notes",
    # these are also used by OpenAPI (for grouping operations).
    application.include_router(notes.router, prefix="/notes", tags=["notes"])

    # install the project router into our app with a prefix & tag too:
    application.include_router(project.router, prefix="/project", tags=["project"])
    
    # install the project invite router into our app with a prefix & tag too:
    application.include_router(invite.router, prefix="/proj_invite", tags=["proj_invite"])
    
    # install the memo router into our app with a prefix & tag too:
    application.include_router(memo.router, prefix="/memo", tags=["memo"])
    
    # install the comment router into our app with a prefix & tag too:
    application.include_router(comment.router, prefix="/comment", tags=["comment"])
    
    # install the aichat router into our app with a prefix & tag too:
    application.include_router(aichat.router, prefix="/aichat", tags=["aichat"])

    # install the video router into our app with a prefix & tag too:
    application.include_router(user_action.router, prefix="/user_action", tags=["user_action"])

    # install the video router into our app with a prefix & tag too:
    application.include_router(video.router, prefix="/video", tags=["video"])

    # install the upload router into our app with a prefix & tag too:
    application.include_router(upload.router, prefix="/upload", tags=["upload"])

    # install the backups router into our app with a prefix & tag too:
    application.include_router(backups.router, prefix="/backups", tags=["backups"])

    # install the users htmlpages router into our app with tag too:
    application.include_router(users_htmlpages.router, tags=["user-pages"])

    # install the html pages router into our app with tag too:
    application.include_router(htmlpages.router, tags=["general-pages"])
    
    return application


# and instantiate it:
app = create_application()

