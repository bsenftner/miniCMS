from fastapi import APIRouter, Header, Request, Response, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

import os
from typing import BinaryIO

from app import config
from app.api import crud
from app.api.users import get_current_active_user, user_has_role
from app.api.user_action import UserAction, UserActionLevel
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





def send_bytes_range_requests(
    file_obj: BinaryIO, start: int, end: int, chunk_size: int = 10_000
):
    """Send a file in chunks using Range Requests specification RFC7233

    `start` and `end` parameters are inclusive due to specification
    """
    with file_obj as f:
        f.seek(start)
        while (pos := f.tell()) <= end:
            read_size = min(chunk_size, end + 1 - pos)
            yield f.read(read_size)


def _get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range():
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f"Invalid request range (Range:{range_header!r})",
        )

    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] != "" else 0
        end = int(h[1]) if h[1] != "" else file_size - 1
    except ValueError:
        raise _invalid_range()

    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end


def range_requests_response(
    request: Request, file_path: str, content_type: str
):
    """Returns StreamingResponse using Range Requests of a given file"""

    file_size = os.stat(file_path).st_size
    range_header = request.headers.get("range")

    headers = {
        "content-type": content_type,
        "accept-ranges": "bytes",
        "content-encoding": "identity",
        "content-length": str(file_size),
        "access-control-expose-headers": (
            "content-type, accept-ranges, content-length, "
            "content-range, content-encoding"
        ),
    }
    start = 0
    end = file_size - 1
    status_code = status.HTTP_200_OK

    if range_header is not None:
        start, end = _get_range_header(range_header, file_size)
        size = end - start + 1
        headers["content-length"] = str(size)
        headers["content-range"] = f"bytes {start}-{end}/{file_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT

    return StreamingResponse(
        send_bytes_range_requests(open(file_path, mode="rb"), start, end),
        headers=headers,
        status_code=status_code,
    )
    
# ------------------------------------------------------------------------------------------------------------------
# endpoint to play video files located inside a project's files directory
@router.get("/project/{projectid}/{video_file}", status_code=206) 
async def project_video_endpoint(request: Request,
                                 projectid: int, 
                                 video_file: str, 
                                 range: str = Header(None),
                                 current_user: UserInDB = Depends(get_current_active_user)):
    
    config.log.info(f"projectid is >{projectid}<")
    config.log.info(f"video_file is >{video_file}<")
    config.log.info(f"range is >{range}<")
    
    proj: ProjectDB = await crud.get_project(projectid)
    if proj is None:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, not found" )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    tag = await crud.get_tag( proj.tagid )
    if not tag:
        await crud.rememberUserAction( current_user.userid,  
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, '{proj.name}', Tag not found" )
        raise HTTPException(status_code=500, detail="Project Tag not found")
    
    weAreAllowed = crud.user_has_project_access( current_user, proj, tag )
    if not weAreAllowed:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_PLAY_PROJECT_VIDEO'), 
                                       f"Project {projectid}, '{proj.name}', not authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access project.")
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('PLAY_PROJECT_VIDEO'), 
                                   f"project {projectid}, video '{video_file}'" )
    
    
    video_path = config.get_base_path() / 'uploads' / tag.text / video_file
    
    return range_requests_response( request, file_path=video_path, content_type="video/mp4" )
    
    """ start, end = 0, 0
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
        return Response(data, status_code=206, headers=headers, media_type="video/mp4") """
