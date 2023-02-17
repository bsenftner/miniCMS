from fastapi import APIRouter, Header, Response, Depends, HTTPException, status

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role, UserAction
from app.api.models import UserInDB, ProjectDB

# create a local router for paths created in this file
router = APIRouter()


# ------------------------------------------------------------------------------------------------------------------
# endpoint to play video files located inside the "app/static/video" directory
@router.get("/{video_file}", status_code=200) 
async def video_endpoint(video_file: str, range: str = Header(None)):
    
    config.log.info(f"video_file is >{video_file}<")
    config.log.info(f"range is >{range}<")
    
    start, end = 0, 0
    if range:
        start, end = range.replace("bytes=", "").split("-")
    
    start = int(start)
    
    CHUNK_SIZE = 1024*1024
    end = int(end) if end else start + CHUNK_SIZE
    
    video_path = config.get_base_path() / 'static/uploads' / video_file
    
    # config.log.info(f"video path is {video_path}")
    
    with open(video_path, "rb") as video:
        # config.log.info(f"video opened!")
        video.seek(start)
        data = video.read(end - start)
        filesize = str(video_path.stat().st_size)
        headers = {
            'Content-Range': f'bytes {str(start)}-{str(end)}/{filesize}',
            'Accept-Ranges': 'bytes'
        }
        return Response(data, status_code=206, headers=headers, media_type="video/mp4")


# ------------------------------------------------------------------------------------------------------------------
# endpoint to play video files located inside a project's files directory
@router.get("/project/{projectid}/{video_file}", status_code=200) 
async def project_video_endpoint(projectid: int, 
                                 video_file: str, 
                                 range: str = Header(None),
                                 current_user: UserInDB = Depends(get_current_active_user)):
    
    config.log.info(f"projectid is >{projectid}<")
    config.log.info(f"video_file is >{video_file}<")
    config.log.info(f"range is >{range}<")
    
    proj: ProjectDB = await crud.get_project(projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid,  UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, UserAction.index('PLAY_PROJECT_VIDEO'), 
                                   f"project {projectid}, video '{video_file}'" )
    
    start, end = 0, 0
    if range:
        start, end = range.replace("bytes=", "").split("-")
    
    start = int(start)
    
    CHUNK_SIZE = 1024*1024
    end = int(end) if end else start + CHUNK_SIZE
    
    video_path = config.get_base_path() / 'uploads' / tag.text / video_file
    
    # config.log.info(f"video path is {video_path}")
    
    with open(video_path, "rb") as video:
        # config.log.info(f"video opened!")
        video.seek(start)
        data = video.read(end - start)
        filesize = str(video_path.stat().st_size)
        headers = {
            'Content-Range': f'bytes {str(start)}-{str(end)}/{filesize}',
            'Accept-Ranges': 'bytes'
        }
        return Response(data, status_code=206, headers=headers, media_type="video/mp4")
