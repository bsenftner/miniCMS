from typing import List, Tuple

from sqlalchemy import asc 

from app.api.models import NoteSchema, MemoSchema, UserReg, UserInDB, UserPublic
from app.api.models import MemoDB, NoteDB, CommentSchema, CommentDB, TagDB, basicTextPayload
from app.api.models import ProjectSchema, ProjectDB, UserActionCreate, UserActionDB, ProjectFileCreate
from app.api.models import ChatbotCreate, ChatbotDB, AiChatCreate, AiChatDB, ProjectInviteCreate
from app.api.models import ProjectInviteDB, ProjectFileDB, ProjectInviteUpdate

from app.db import DatabaseMgr, get_database_mgr

from app.api.users import user_has_role

from app.config import log

from app.worker import celery_app
from celery.exceptions import TimeoutError

# ---------------------------------------------------------------------------------------
async def rememberUserAction( userid: int, actionLevel: int, action: int, desc: str ):
    payload = UserActionCreate(actionLevel=actionLevel, actionCode=action, description=desc)
    await post_user_action( payload, userid )
    
# -----------------------------------------------------------------------------------------
# for creating new user actions
async def post_user_action(payload: UserActionCreate, userid: int ):
    # log.info(f"post_user_action: payload is {payload}")
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_action_table().insert().values(userid=userid,
                                                      actionLevel=payload.actionLevel,
                                                      actionCode=payload.actionCode,
                                                      description=payload.description)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)


# -----------------------------------------------------------------------------------------
# for getting individual user actions by id:
async def get_user_action(actionid: int) -> UserActionDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_action_table().select().where(actionid == db_mgr.get_action_table().c.actionid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all user actions:
async def get_all_user_actions() -> List[UserActionDB]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_action_table().select().order_by(asc(db_mgr.get_action_table().c.actionid))
    return await db_mgr.get_db().fetch_all(query=query)   

# -----------------------------------------------------------------------------------------
# returns all user actions attributed to a user
async def get_all_this_users_actions(user: UserInDB, limit: int = 25, offset: int = 0) -> List[UserActionDB]:
    
    # log.info(f"get_all_this_users_actions: limit is {limit}, offset is {offset}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_action_table().select().where(user.userid == db_mgr.get_action_table().c.userid).limit(limit).offset(offset)
    actionList = await db_mgr.get_db().fetch_all(query=query)   
            
    return actionList

# -----------------------------------------------------------------------------------------
# returns the number of the user actions attributed to a user
async def get_this_users_action_count(user: UserInDB):
    
    # log.info(f"get_this_users_action_count: user is {user.userid}, {user.username}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    
    # query = db_mgr.get_action_table().select().filter_by().count()
    query = "SELECT COUNT(*) FROM action WHERE userid=" + str(user.userid)
    
    result = await db_mgr.get_db().fetch_one(query=query)
    
    # log.info(f"get_this_users_action_count: result is {result['count']}:")
    # log.info({**result})
    
    return result['count']



# -----------------------------------------------------------------------------------------
# for creating new tags
async def post_tag(payload: basicTextPayload):
    log.info(f"post_tag: payload is {payload}")
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_tag_table().insert().values(text=payload.text)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting tags:
async def get_tag(id: int) -> TagDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_tag_table().select().where(id == db_mgr.get_tag_table().c.tagid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# for getting tags:
async def get_tag_by_name(text: str) -> TagDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_tag_table().select().where(text == db_mgr.get_tag_table().c.text)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all tags:
async def get_all_tags() -> List[TagDB]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_tag_table().select().order_by(asc(db_mgr.get_tag_table().c.tagid))
    return await db_mgr.get_db().fetch_all(query=query)   

# -----------------------------------------------------------------------------------------
# update a tag:
async def put_tag(tagid: int, payload: basicTextPayload):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_tag_table()
        .update()
        .where(tagid == db_mgr.get_tag_table().c.tagid)
        .values(text=payload.text)
        .returning(db_mgr.get_tag_table().c.tagid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# delete a tag. 
async def delete_tag(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_tag_table().delete().where(id == db_mgr.get_tag_table().c.tagid)
    return await db_mgr.get_db().execute(query=query)



# ----------------------------------------------------------------------------------------------
# a utility for getting the permission to access a project
def user_has_project_access( user: UserInDB, proj: ProjectDB, projTag: TagDB ) -> bool:
    # first unverified automatically get denied access:
    weAreAllowed = not user_has_role(user, 'unverified')
    if weAreAllowed:
        # next admins automatically get access:
        weAreAllowed = user_has_role(user, 'admin')
        if not weAreAllowed:
            # if we're the creator:
            if proj.userid == user.userid:
                weAreAllowed = True
            # for everyone else must be project member and project is published:
            elif user_has_role(user, projTag.text) and proj.status == 'published':
                weAreAllowed = True
                
    return weAreAllowed

# ----------------------------------------------------------------------------------------------
# a utility for getting chatbotEditor permission on a project
def user_has_project_chatbotEditor_access( user: UserInDB, proj: ProjectDB, cbeTag: TagDB ) -> bool:
    # first unverified automatically get denied access:
    weAreAllowed = not user_has_role(user, 'unverified')
    if weAreAllowed:
        # next admins automatically get access:
        weAreAllowed = user_has_role(user, 'admin')
        if not weAreAllowed:
            # if we're the creator:
            if proj.userid == user.userid:
                weAreAllowed = True
            # for everyone else must be project member and project is published:
            elif user_has_role(user, cbeTag.text) and proj.status == 'published':
                weAreAllowed = True
                
    return weAreAllowed

# ----------------------------------------------------------------------------------------------
# a utility for getting the permission to access a project
async def user_has_project_access_by_id( user: UserInDB, projectid: int ) -> bool:
    # first unverified automatically get denied access:
    weAreAllowed = not user_has_role(user, 'unverified')
    if weAreAllowed:
        # next admins automatically get access:
        weAreAllowed = user_has_role(user, 'admin')
        if not weAreAllowed:
            # for everyone else:
            proj, tag = await get_project_and_tag(projectid)
            # proj: ProjectDB = await get_project(projectid)
            if not proj:
                weAreAllowed = False
            else:
                # tag: TagDB = await get_tag(proj.tagid)
                if not tag:
                    weAreAllowed = False
                else:
                    weAreAllowed = user_has_project_access(user, proj, tag)
    return weAreAllowed

# -----------------------------------------------------------------------------------------
# for creating new projects
async def post_project(payload: ProjectSchema):

    #log.info(f"post_project: payload {payload}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_project_table().insert().values(name=payload.name, 
                                                       text=payload.text,
                                                       userid=payload.userid,
                                                       username=payload.username,
                                                       status=payload.status,
                                                       tagid=payload.tagid,
                                                       cbetagid=payload.cbetagid)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting projects:
async def get_project(id: int) -> ProjectDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().select().where(id == db_mgr.get_project_table().c.projectid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
async def get_project_and_tag(projectid: int) -> Tuple:
    
    proj: ProjectDB = await get_project(projectid)
    if not proj:
        return (None, None)
    
    # access permission for this project
    tag: TagDB = await get_tag(proj.tagid)
    if not tag:
        return (proj, None)
    
    return (proj, tag)

# -----------------------------------------------------------------------------------------
async def get_project_both_tags(projectid: int) -> Tuple:
    
    proj: ProjectDB = await get_project(projectid)
    if not proj:
        return (None, None, None)
    
    # access permission for this project
    tag: TagDB = await get_tag(proj.tagid)
    if not tag:
        return (proj, None, None)
    
    # chatbot edit permission for this project
    cbetag: TagDB = await get_tag(proj.cbetagid)
    if not cbetag:
        return (proj, tag, None)
    
    return (proj, tag, cbetag)

# -----------------------------------------------------------------------------------------
# for getting projects by their name:
async def get_project_by_name(name: str) -> ProjectDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().select().where(name == db_mgr.get_project_table().c.name)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# for getting projects by their tagid:
async def get_project_by_tagid(tagid: int) -> ProjectDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().select().where(tagid == db_mgr.get_project_table().c.tagid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all projects user has access
async def get_all_projects(user: UserInDB) -> List[ProjectDB]:
    
    # log.info(f"get_all_projects: user is {user}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().select().order_by(asc(db_mgr.get_project_table().c.projectid))
    projectList = await db_mgr.get_db().fetch_all(query=query)   

    # now filter them by the roles held by the user:
    finalList = []
    for proj in projectList:
        tag: TagDB = await get_tag(proj.tagid)
        if tag:
            if user_has_project_access( user, proj, tag ):
                finalList.append(proj)
            
    return finalList

# -----------------------------------------------------------------------------------------
# update a project:
async def put_project(projectid: int, payload: ProjectSchema):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_project_table()
        .update()
        .where(projectid == db_mgr.get_project_table().c.projectid)
        .values(name=payload.name, 
                text=payload.text,
                userid=payload.userid,
                username=payload.username,
                status=payload.status,
                tagid=payload.tagid,
                cbetagid=payload.cbetagid)
        .returning(db_mgr.get_project_table().c.projectid)
    )
    return await db_mgr.get_db().execute(query=query)

# ---------------------------------------------------------------------------------------------
# delete a project. Note: this does not validate if the current user should be able to do this;
# that logic is in the delete_project() router.delete endpoint handler. 
async def delete_project(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().delete().where(id == db_mgr.get_project_table().c.projectid)
    return await db_mgr.get_db().execute(query=query)


# -----------------------------------------------------------------------------------------
# for creating new projectfiles 
async def post_projectfile(payload: ProjectFileCreate, userid: int ):

    log.info(f"post_projectfile: payload {payload}")
    
    # do not allow duplicates!
    projFile: ProjectFileDB = await get_projectfile_by_filename(payload.filename, payload.projectid)
    if projFile:
        return None
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_projectfile_table().insert().values(filename=payload.filename, 
                                                           projectid=payload.projectid,
                                                           modifiable=payload.modifiable,
                                                           userid=userid,
                                                           version=1,
                                                           status="latest",
                                                           checked_userid=None,
                                                           checked_date=None)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting projectfiles:
async def get_projectfile(id: int) -> ProjectFileDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_projectfile_table().select().where(id == db_mgr.get_projectfile_table().c.pfid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# for getting projectfiles by their name and project id:
async def get_projectfile_by_filename(filename: str, projectid: int) -> ProjectFileDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_projectfile_table().select()\
        .where(projectid == db_mgr.get_projectfile_table().c.projectid)\
        .where(filename == db_mgr.get_projectfile_table().c.filename)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all projects user has access
async def get_project_projectfiles(projectid: int) -> List[ProjectDB]:
    
    log.info(f"get_project_projectfiles: projectid {projectid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_projectfile_table().select().where(projectid == db_mgr.get_projectfile_table().c.projectid)
    projectFileList = await db_mgr.get_db().fetch_all(query=query)   
            
    return projectFileList

# -----------------------------------------------------------------------------------------
# update a projectfile, only the shown fields can change: 
async def put_projectfile(projFile: ProjectFileDB):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_projectfile_table()
        .update()
        .where(projFile.pfid == db_mgr.get_projectfile_table().c.pfid)
        .values(filename=projFile.filename, 
                version=projFile.version, 
                checked_userid=projFile.checked_userid,
                checked_date=projFile.checked_date)
        .returning(db_mgr.get_projectfile_table().c.pfid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# delete a projectfile:
async def delete_projectfile(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_projectfile_table().delete().where(id == db_mgr.get_projectfile_table().c.pfid)
    return await db_mgr.get_db().execute(query=query)



# ----------------------------------------------------------------------------------------------
# a utility for getting the permission to access a memo
async def user_has_memo_access( user: UserInDB, memo: MemoDB ) -> bool:
    # first admins automatically get access:
    weAreAllowed = user_has_role(user, 'admin') or memo.access == 'public'
    if not weAreAllowed:
        # for everyone else, first make sure user has the memo's project access:
        weAreAllowed = await user_has_project_access_by_id(user, memo.projectid)
        if weAreAllowed:
            # user has project access, is the memo published?
            if memo.status == 'published':
                # if user is admin they are already in, if memo is public they are already in...
                if memo.access == 'staff':
                    weAreAllowed = True
                else:
                    weAreAllowed = False
                # else memo.access must be 'admin', and we know user is not admin here
            elif memo.userid == user.userid:
                # memo is unpublished, but user is author, so access is granted (so they can finish the memo!)
                weAreAllowed = True
            else:
                # memo is unpublished, user is not author or admin
                weAreAllowed = False
                
    return weAreAllowed

# -----------------------------------------------------------------------------------------
# for creating new memos
async def post_memo(payload: MemoSchema, user_id: int):    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_memo_table().insert().values(title=payload.title, 
                                                    text=payload.text,
                                                    status=payload.status,
                                                    access=payload.access,
                                                    tags=payload.tags,
                                                    userid=payload.userid,
                                                    username=payload.username,
                                                    projectid=payload.projectid)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting memos:
async def get_memo(id: int) -> MemoDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_memo_table().select().where(id == db_mgr.get_memo_table().c.memoid)
    return await db_mgr.get_db().fetch_one(query=query)
    
# -----------------------------------------------------------------------------------------
# returns all memo posts:
async def get_all_memos(user: UserInDB) -> List[MemoDB]:
    
    # log.info(f"get_all_memos: working with user {user}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_memo_table().select().order_by(asc(db_mgr.get_memo_table().c.memoid))
    
    memoList = await db_mgr.get_db().fetch_all(query=query)
    
    # now filter them by the roles held by the user:
    finalMemoList = []
    for m in memoList:
        # log.info(f"get_all_memos: working with memo.memoid {m.memoid}")
        # log.info(f"get_all_memos: memo.access {m.access}")
        user_access = await user_has_memo_access( user, m )
        if user_access:
            if m.status == 'unpublished':
                m.title += ' (unpublished)'
            elif m.status == 'archived':
                m.title += ' (archived)'
            if m.access == 'admin':
                m.title += ' (admin)'
            m.title += ' - by ' + m.username
            finalMemoList.append(m)
            
    return finalMemoList

# -----------------------------------------------------------------------------------------
# returns all public access memo posts:
async def get_all_public_memos() -> List[MemoDB]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_memo_table().select().order_by(asc(db_mgr.get_memo_table().c.memoid))
    
    memoList = await db_mgr.get_db().fetch_all(query=query)
    
    # now filter them for memos with 'public' in their access strings:
    finalMemoList = []
    for m in memoList:
        if 'public' == m.access and 'published' == m.status:
            finalMemoList.append(m)
            
    return finalMemoList

# -----------------------------------------------------------------------------------------
# returns all project memo posts:
async def get_all_project_memos(user: UserInDB, projectid: int) -> List[MemoDB]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_memo_table().select().where(projectid == db_mgr.get_memo_table().c.projectid)\
                                            .order_by(asc(db_mgr.get_memo_table().c.memoid))
    
    memoList = await db_mgr.get_db().fetch_all(query=query)
            
     # now filter them by the roles held by the user:
    finalMemoList = []
    for m in memoList:
        user_access = await user_has_memo_access( user, m )
        if user_access:
            if m.status == 'unpublished':
                m.title += ' (unpublished)'
            elif m.status == 'archived':
                m.title += ' (archived)'
            if m.access == 'admin':
                m.title += ' (admin)'
            m.title += ' - by ' + m.username
            finalMemoList.append(m)
            
    return finalMemoList

# -----------------------------------------------------------------------------------------
# update a memo:
async def put_memo(memoid: int, userid: int, payload: MemoSchema):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_memo_table()
        .update()
        .where(memoid == db_mgr.get_memo_table().c.memoid)
        .values(title=payload.title, 
                text=payload.text, 
                status=payload.status, 
                access=payload.access, 
                tags=payload.tags,
                userid=payload.userid,
                username=payload.username,
                projectid=payload.projectid)
        .returning(db_mgr.get_memo_table().c.memoid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# delete a memo. Note: this does not validate if the current user should be able to do this;
# that logic is in the delete_memo() router.delete endpoint handler. 
async def delete_memo(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_memo_table().delete().where(id == db_mgr.get_memo_table().c.memoid)
    return await db_mgr.get_db().execute(query=query)



# -----------------------------------------------------------------------------------------
# for creating new comments
async def post_comment(payload: CommentSchema):
    # log.info(f"post_comment: here! got {payload}")
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_comment_table().insert().values(text=payload.text, 
                                                       memoid=payload.memoid,
                                                       userid=payload.userid, 
                                                       username=payload.username,
                                                       parent=payload.parent)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting comments:
async def get_comment(commid: int) -> CommentDB:
    # log.info(f"get_comment: getting comment with commid {commid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_comment_table().select().where(commid == db_mgr.get_comment_table().c.commid)
    
    # log.info(f"get_comment: query built...")
    
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all comments for a given memo:
async def get_all_memo_comments(memoid: int) -> List[CommentDB]:
    
    # log.info(f"get_all_memo_comments: getting comments for memo with id {memoid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # query = db_mgr.get_comment_table().select().where(memoid == db_mgr.get_comment_table().c.memoid).order_by(asc(db_mgr.get_comment_table().c.commid))
    query = db_mgr.get_comment_table().select().where(memoid == db_mgr.get_comment_table().c.memoid)
    
    commIdList = await db_mgr.get_db().fetch_all(query=query)
        
    finalCommList = []
    for c in commIdList:
        # commid = c.commid
        # log.info(f"get_all_memo_comments: preping comment with id {commid}")
        fullComm = CommentDB( commid = c.commid,
                              text = c.text,
                              memoid = c.memoid,
                              userid = c.userid,
                              username = c.username,
                              parent = c.parent,
                              created_date = c.created_date)
        finalCommList.append(fullComm)
            
    # log.info(f"get_all_memo_comments: finalCommList {finalCommList}")
            
    return finalCommList

# ---------------------------------------------------------------------------------------------
# delete a comment. Note: this does not validate if the current user should be able to do this;
# that logic is in the delete_comment() router.delete endpoint handler. 
async def delete_comment(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_comment_table().delete().where(id == db_mgr.get_comment_table().c.commid)
    return await db_mgr.get_db().execute(query=query)




# -----------------------------------------------------------------------------------------
# for creating new notes
async def post_note(payload: NoteSchema, owner: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_notes_table().insert().values(title=payload.title, 
                                                     description=payload.description,
                                                     data=payload.data,
                                                     owner=owner)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting notes:
async def get_note(id: int) -> NoteDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_notes_table().select().where(id == db_mgr.get_notes_table().c.id)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# for getting notes by their title:
async def get_note_by_title(title: str) -> NoteDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_notes_table().select().where(title == db_mgr.get_notes_table().c.title)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all notes:
async def get_all_notes() -> List[NoteDB]:
    db_mgr = get_database_mgr()
    query = db_mgr.get_notes_table().select().order_by(asc(db_mgr.get_notes_table().c.id))
    return await db_mgr.get_db().fetch_all(query=query)

# -----------------------------------------------------------------------------------------
# update a note:
async def put_note(id: int, payload: NoteSchema, owner: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_notes_table()
        .update()
        .where(id == db_mgr.get_notes_table().c.id)
        .values(title=payload.title, 
                description=payload.description, 
                data=payload.data,
                owner=owner)
        .returning(db_mgr.get_notes_table().c.id)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# delete a note:
async def delete_note(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_notes_table().delete().where(id == db_mgr.get_notes_table().c.id)
    return await db_mgr.get_db().execute(query=query)




# -----------------------------------------------------------------------------------------
# for creating new users:
async def post_user(user: UserReg, 
                    hashed_password: str,
                    verify_code: str,
                    roles: str):
    '''crud action to create a new user via PRE-VALIDATED data'''
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().insert().values( username=user.username, 
                                                      hashed_password=hashed_password,
                                                      verify_code=verify_code,
                                                      email=user.email,
                                                      roles=roles )
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query)
    

# -----------------------------------------------------------------------------------------
# a few methods for getting users:
async def get_user_by_id(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().select().where(id == db_mgr.get_users_table().c.userid)
    return await db_mgr.get_db().fetch_one(query=query)

async def get_user_by_name(username: str):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().select().where(db_mgr.get_users_table().c.username == username)
    return await db_mgr.get_db().fetch_one(query)

async def get_user_by_email(email: str):
    db_mgr = get_database_mgr()
    query = db_mgr.get_users_table().select().where(db_mgr.get_users_table().c.email == email)
    return await db_mgr.get_db().fetch_one(query)

# -----------------------------------------------------------------------------------------
# returns all users:
async def get_all_users() -> List[UserPublic]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().select().order_by(asc(db_mgr.get_users_table().c.userid))
    
    userList = await db_mgr.get_db().fetch_all(query=query)
            
    # now filter them:
    finalUserList = []
    for u in userList:
        up = UserPublic(username = u.username, userid = u.userid, roles = u.roles, email = u.email) 
        finalUserList.append(up)
            
    return finalUserList


# -----------------------------------------------------------------------------------------
# returns all users by role:
async def get_all_users_by_role(role: str) -> List[UserPublic]:
    # first get all the users:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().select().order_by(asc(db_mgr.get_users_table().c.userid))
    userList = await db_mgr.get_db().fetch_all(query=query)
            
    # now filter them:
    finalUserList = []
    for u in userList:
        # break the user's role string into tokens, one for each role:
        roleList = u.roles.split()
        # loop over the roleList retaining those matching the input:
        for r in roleList:
            if r == role:
                up = UserPublic(username = u.username, userid = u.userid, roles = u.roles, email = u.email) 
                finalUserList.append(up)
    
    return finalUserList

# -----------------------------------------------------------------------------------------
# returns all UserDBs by role:
async def get_all_UserDBs_by_role(role: str) -> List[UserInDB]:
    # first get all the users:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_users_table().select().order_by(asc(db_mgr.get_users_table().c.userid))
    userList = await db_mgr.get_db().fetch_all(query=query)
            
    # now filter them:
    finalUserList = []
    for u in userList:
        log.info( f"get_all_UserDBs_by_role: user {u.userid} has roles {u.roles}")
        # break the user's role string into tokens, one for each role:
        roleList = u.roles.split()
        # loop over the roleList retaining those matching the input:
        for r in roleList:
            if r == role: 
                finalUserList.append(u)
    
    return finalUserList

# -----------------------------------------------------------------------------------------
# update a user passed an user id and an updated UserInDB. 
# Note: the id field in the UserInDB is ignored. 
async def put_user(id: int, user: UserInDB):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_users_table()
        .update()
        .where(id == db_mgr.get_users_table().c.userid)
        .values( username=user.username, 
                 hashed_password=user.hashed_password,
                 verify_code=user.verify_code,
                 email=user.email,
                 roles=user.roles
               ).returning(db_mgr.get_users_table().c.userid)
        # .returning(db_mgr.get_users_table().c.userid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# note: there is no user delete, that is accomplished by disabling a user. 
# A user is disabled by adding the "disabled" to their "roles" db field. 




# -----------------------------------------------------------------------------------------
# for creating new AI Chat Roles
async def post_Chatbot(payload: ChatbotCreate, user: UserInDB):
    
    log.info(f"post_Chatbot: here! got {payload} for user {user.userid}, {user.username}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_chatbot_table().insert().values(name=payload.name, 
                                                       prePrompt=payload.prePrompt, 
                                                      model=payload.model, 
                                                       projectid=payload.projectid,
                                                       userid=user.userid, 
                                                       username=user.username)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting AI Chat Roles:
async def get_Chatbot(chatbotid: int) -> ChatbotDB:
    
    log.info(f"get_Chatbot: getting chatbotid {chatbotid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_chatbot_table().select().where(chatbotid == db_mgr.get_chatbot_table().c.chatbotid)
    
    log.info(f"get_Chatbot: query built...")
    
    chatbot: ChatbotDB = await db_mgr.get_db().fetch_one(query=query)
            
    if chatbot:
        log.info(f"get_Chatbot: chatbot.name         '{chatbot.name}'")
        log.info(f"get_Chatbot: chatbot.prePrompt    '{chatbot.prePrompt}'")
        log.info(f"get_Chatbot: chatbot.model        '{chatbot.model}'")
        log.info(f"get_Chatbot: chatbot.chatbotid    '{chatbot.chatbotid}'")
        log.info(f"get_Chatbot: chatbot.projectid    '{chatbot.projectid}'")
        log.info(f"get_Chatbot: chatbot.userid       '{chatbot.userid}'")
        log.info(f"get_Chatbot: chatbot.username     '{chatbot.username}'")
        log.info(f"get_Chatbot: chatbot.created_date '{chatbot.created_date}'")
        log.info(f"get_Chatbot: chatbot.updated_date '{chatbot.updated_date}'")
    else:
        log.info(f"get_Chatbot: returning None")
        
    return chatbot

# -----------------------------------------------------------------------------------------
# returns all ChatbotDB for a given project:
async def get_all_project_Chatbots(projectid: int) -> List[ChatbotDB]:
    
    log.info(f"get_all_project_Chatbots: getting ai chats for project with id {projectid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_chatbot_table().select().where(projectid == db_mgr.get_chatbot_table().c.projectid)
    
    log.info(f"get_all_project_Chatbots: query built...")
    
    chatbotList = await db_mgr.get_db().fetch_all(query=query)
        
    finalList = []
    for c in chatbotList:
        chatbot = ChatbotDB( chatbotid = c.chatbotid,
                             name = c.name,
                             prePrompt = c.prePrompt,
                             model = c.model,
                             projectid = c.projectid,
                             userid = c.userid,
                             username = c.username,
                             created_date = c.created_date,
                             updated_date = c.updated_date)
        #
        log.info(f"get_all_project_Chatbots: id           {chatbot.chatbotid}")
        log.info(f"get_all_project_Chatbots: name         {chatbot.name}")
        log.info(f"get_all_project_Chatbots: prePrompt    {chatbot.prePrompt}")
        log.info(f"get_all_project_Chatbots: model        {chatbot.model}")
        log.info(f"get_all_project_Chatbots: projectid    {chatbot.projectid}")
        log.info(f"get_all_project_Chatbots: userid       {chatbot.userid}")
        log.info(f"get_all_project_Chatbots: username     {chatbot.username}")
        log.info(f"get_all_project_Chatbots: created_date {chatbot.created_date}")
        log.info(f"get_all_project_Chatbots: updated_date {chatbot.updated_date}")
        #
        finalList.append(chatbot)
            
    # log.info(f"get_all_project_Chatbots : finalList {finalList}")
            
    return finalList

# -----------------------------------------------------------------------------------------
# update an ChatbotDB. 
async def put_Chatbot(chatbot: ChatbotDB):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_chatbot_table()
        .update()
        .where(chatbot.chatbotid == db_mgr.get_chatbot_table().c.chatbotid)
        .values( name = chatbot.name,
                 prePrompt = chatbot.prePrompt,
                 model = chatbot.model ).returning(db_mgr.get_chatbot_table().c.chatbotid)
    )
    return await db_mgr.get_db().execute(query=query)

# note: no delete for AI Chat Roles 



# -----------------------------------------------------------------------------------------
# for creating new AI Chat exchanges
async def post_aiChat(prompt: str, chatbot: ChatbotDB, user: UserInDB):
    
    log.info(f"post_aiChat: here! user {user.userid}, {user.username} asks {prompt}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_aichat_table().insert().values(prePrompt=chatbot.prePrompt, 
                                                      prompt=prompt, 
                                                      reply='', 
                                                      model=chatbot.model, 
                                                      status='ready', 
                                                      taskid='none',
                                                      chatbotid=chatbot.chatbotid,
                                                      projectid=chatbot.projectid,
                                                      userid=user.userid, 
                                                      username=user.username)
    
    log.info(f"post_aiChat: query build...")
    
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# ------------------------------------------------------------------------------------------------
# communications with OpenAI take place in a Celery Task, and this is used to recover the results:
async def resolve_aichat_task_results( aichat: AiChatDB ) -> AiChatDB:
    # Celery task results recovery logic:
    task_result = celery_app.AsyncResult(aichat.taskid)
    if task_result.status == 'SUCCESS':
        try:
            resObj = task_result.get(timeout=0.001)
            aichat.reply = resObj.reply 
            aichat.reply = "<p>" + aichat.reply.replace("\n", "<br>") + "</p>"
            aichat.status = resObj.status 
            await put_aichat( aichat )
        except TimeoutError:
            log.info(f"resolve_aichat_task_results: TimeoutError!")
    elif task_result.status == 'FAILURE':
        task_result.forget()
        aichat.status = 'failed'
        await put_aichat( aichat )
            
    return aichat

# -----------------------------------------------------------------------------------------
# for getting AI Chat exchanges:
async def get_aiChat(aichatid: int) -> AiChatDB:
    
    # log.info(f"get_aiChat: getting aichatid {aichatid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_aichat_table().select().where(aichatid == db_mgr.get_aichat_table().c.aichatid)
    
    # log.info(f"get_aiChat: query built...")
    
    aichat: AiChatDB = await db_mgr.get_db().fetch_one(query=query)
    
    # special Celery task results recovery logic:
    if aichat.status == 'inuse':
        aichat = await resolve_aichat_task_results( aichat )
            
    return aichat


# -----------------------------------------------------------------------------------------
# returns all AiChatDB for a given project:
async def get_all_project_aiChats(projectid: int) -> List[AiChatDB]:
    
    # log.info(f"get_all_project_aiChats: getting ai chats for project with id {projectid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_aichat_table().select().where(projectid == db_mgr.get_aichat_table().c.projectid)
    
    # log.info(f"get_all_project_aiChats: query built...")
    
    chatList = await db_mgr.get_db().fetch_all(query=query)
        
    finalList = []
    for c in chatList:
        # aichatid = c.aichatid
        # log.info(f"get_all_project_aiChats: preping comment with id {aichatid}")
        aiChatExchange = AiChatDB( aichatid = c.aichatid,
                                   prePrompt = c.prePrompt,
                                   prompt = c.prompt,
                                   reply = c.reply,
                                   model = c.model,
                                   status = c.status,
                                   taskid = c.taskid,
                                   chatbotid = c.chatbotid,
                                   projectid = c.projectid,
                                   userid = c.userid,
                                   username = c.username,
                                   created_date = c.created_date,
                                   updated_date = c.updated_date)
        #
        # special Celery task results recovery logic:
        if aiChatExchange.status == 'inuse':
            aiChatExchange = await resolve_aichat_task_results( aiChatExchange )
        #
        finalList.append(aiChatExchange)
            
    # log.info(f"get_all_project_aiChats: finalList {finalList}")
            
    return finalList

# -----------------------------------------------------------------------------------------
# returns all AiChatDB for a given "conversation":
async def get_all_conversation_aiChats(projectid: int, aichatid: int) -> List[AiChatDB]:
    
    # log.info(f"get_all_conversation_aiChats: getting ai chats for aichatid {aichatid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_aichat_table().select().where(projectid == db_mgr.get_aichat_table().c.projectid)
    
    # log.info(f"get_all_conversation_aiChats: query built...")
    
    chatList = await db_mgr.get_db().fetch_all(query=query)
        
    finalList = []
    for c in chatList:
        aichatid = c.aichatid
        parent = c.parent
        if c.aichatid == aichatid or c.parent == aichatid:
            # log.info(f"get_all_conversation_aiChats: preping comment with id {aichatid}")
            aiChatExchange = AiChatDB( aichatid = c.aichatid,
                                       prePrompt = c.prePrompt,
                                       prompt = c.prompt,
                                       reply = c.reply,
                                       model = c.model,
                                       status = c.status,
                                       taskid = c.taskid,
                                       chatbotid = c.chatbotid,
                                       projectid = c.projectid,
                                       userid = c.userid,
                                       username = c.username,
                                       created_date = c.created_date)
            #
            # special Celery task results recovery logic:
            if aiChatExchange.status == 'inuse':
                aiChatExchange = await resolve_aichat_task_results( aiChatExchange )
            #
            finalList.append(aiChatExchange)
            
    # log.info(f"get_all_conversation_aiChats: finalList {finalList}")
            
    return finalList

# -----------------------------------------------------------------------------------------
# update an AiChatDB. 
async def put_aichat(aichat: AiChatDB):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_aichat_table()
        .update()
        .where(aichat.aichatid == db_mgr.get_aichat_table().c.aichatid)
        .values( prePrompt = aichat.prePrompt,
                 prompt = aichat.prompt,
                 reply = aichat.reply,
                 status = aichat.status,
                 taskid = aichat.taskid ).returning(db_mgr.get_aichat_table().c.aichatid)
    )
    return await db_mgr.get_db().execute(query=query)

# note: no delete for AI Chat Exchanges 




# -----------------------------------------------------------------------------------------
# for creating new project invites
async def post_projInvite(payload: ProjectInviteCreate, tag: str, user: UserInDB):
    
    log.info(f"post_projInvite: here! got {payload} by user {user.userid}, {user.username}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_invite_table().insert().values(projectid=payload.projectid, 
                                                      tag=tag, 
                                                      byuserid=user.userid, 
                                                      touserid=payload.touserid, 
                                                      status=0)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting project invites:
async def get_projInvite(projInviteId: int) -> ProjectInviteDB:
    
    # log.info(f"get_projInvite: getting projInviteId {projInviteId}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_invite_table().select().where(projInviteId == db_mgr.get_invite_table().c.inviteid)
    
    # log.info(f"get_projInvite: query built...")
    
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# returns all project invites for a given user:
async def get_user_projInvites(user: UserInDB) -> List[ProjectInviteDB]:
    
    log.info(f"get_user_projInvites: getting project invites for user {user.userid}, {user.username}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_invite_table().select().where(user.userid == db_mgr.get_invite_table().c.touserid)
    
    log.info(f"get_user_projInvites: query built...")
    
    inviteList = await db_mgr.get_db().fetch_all(query=query)
            
    return inviteList

# -----------------------------------------------------------------------------------------
# returns all project invites for a given project:
async def get_project_projInvites(projectid: int) -> List[ProjectInviteDB]:
    
    log.info(f"get_project_projInvites: getting project invites for projeect {projectid}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_invite_table().select().where(projectid == db_mgr.get_invite_table().c.projectid)
    
    log.info(f"get_project_projInvites: query built...")
    
    inviteList = await db_mgr.get_db().fetch_all(query=query)
            
    finalList = []
    for invite in inviteList:
        full = ProjectInviteDB( inviteid = invite.inviteid,
                                projectid = invite.projectid,
                                tag = invite.tag,
                                byuserid = invite.byuserid,
                                touserid = invite.touserid,
                                status = invite.status)
        finalList.append(full)
        
    return finalList

# -----------------------------------------------------------------------------------------
# update a ProjectInviteDB. 
async def put_projInvite( projInviteId: int, inviteUpdate: ProjectInviteUpdate):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = (
        db_mgr.get_invite_table()
        .update()
        .where(projInviteId == db_mgr.get_invite_table().c.inviteid)
        .values( status = inviteUpdate.status ).returning(db_mgr.get_invite_table().c.inviteid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# delete a ProjectInviteDB:
async def delete_projInvite(id: int):
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_invite_table().delete().where(id == db_mgr.get_invite_table().c.inviteid)
    return await db_mgr.get_db().execute(query=query)
