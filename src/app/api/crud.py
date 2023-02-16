from typing import List
from sqlalchemy import asc 

from app.api.models import NoteSchema, MemoSchema, UserReg, UserInDB, UserPublic
from app.api.models import MemoDB, NoteDB, CommentSchema, CommentDB, TagDB, basicTextPayload
from app.api.models import ProjectSchema, ProjectDB, UserActionRec, UserActionDB

from app.db import DatabaseMgr, get_database_mgr

from app.api.users import user_has_role

from app.config import log


# ---------------------------------------------------------------------------------------
async def rememberUserAction( userid: int, action: int, desc: str ):
    payload = UserActionRec(actionCode=action, description=desc)
    await post_user_action( payload, userid )
    
# -----------------------------------------------------------------------------------------
# for creating new user actions
async def post_user_action(payload: UserActionRec, userid: int ):
    log.info(f"post_user_action: payload is {payload}")
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_action_table().insert().values(userid=userid,
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
async def get_all_this_users_actions(user: UserInDB) -> List[UserActionDB]:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_action_table().select().where(user.userid == db_mgr.get_action_table().c.userid)
    actionList = await db_mgr.get_db().fetch_all(query=query)   
            
    return actionList

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
    # first admins automatically get access:
    weAreAllowed = user_has_role(user, 'admin')
    if not weAreAllowed:
        # for everyone else:
        if user_has_role(user, projTag.text) and proj.status == 'published':
            weAreAllowed = True
    return weAreAllowed

# ----------------------------------------------------------------------------------------------
# a utility for getting the permission to access a project
async def user_has_project_access_by_id( user: UserInDB, projectid: int ) -> bool:
    # first admins automatically get access:
    weAreAllowed = user_has_role(user, 'admin')
    if not weAreAllowed:
        # for everyone else:
        proj: ProjectDB = await get_project(projectid)
        if not proj:
            weAreAllowed = False
        else:
            tag: TagDB = await get_tag(proj.tagid)
            if not tag:
                weAreAllowed = False
            else:
                weAreAllowed = user_has_project_access(user, proj, tag)
    return weAreAllowed

# -----------------------------------------------------------------------------------------
# for creating new projects
async def post_project(payload: ProjectSchema):
    log.info(f"post_project: here!")
    log.info(f"post_project is {payload}")
    
    db_mgr: DatabaseMgr = get_database_mgr()
    # Creates a SQLAlchemy insert object expression query
    query = db_mgr.get_project_table().insert().values(name=payload.name, 
                                                       text=payload.text,
                                                       userid=payload.userid,
                                                       username=payload.username,
                                                       status=payload.status,
                                                       tagid=payload.tagid)
    # Executes the query and returns the generated ID
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# for getting projects:
async def get_project(id: int) -> ProjectDB:
    db_mgr: DatabaseMgr = get_database_mgr()
    query = db_mgr.get_project_table().select().where(id == db_mgr.get_project_table().c.projectid)
    return await db_mgr.get_db().fetch_one(query=query)

# -----------------------------------------------------------------------------------------
# for getting projects by their name:
async def get_project_by_name(name: int) -> ProjectDB:
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
                tagid=payload.tagid)
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
                weAreAllowed = True
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
    log.info(f"post_memo: here!")
    log.info(f"payload is {payload}")
    
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
    # query = db_mgr.get_memo_table().select().order_by(asc(db_mgr.get_memo_table().c.memoid))
    
    query = db_mgr.get_memo_table().select().where(projectid == db_mgr.get_memo_table().c.projectid).order_by(asc(db_mgr.get_memo_table().c.memoid))
    
    memoList = await db_mgr.get_db().fetch_all(query=query)
            
     # now filter them by the roles held by the user:
    finalMemoList = []
    for m in memoList:
        user_access = await user_has_memo_access( user, m )
        if user_access:
            if m.status == 'unpublished':
                m.title += ' (unpublished)'
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
        .returning(db_mgr.get_users_table().c.userid)
    )
    return await db_mgr.get_db().execute(query=query)

# -----------------------------------------------------------------------------------------
# note: there is no user delete, that is accomplished by disabling a user. 
# A user is disabled by adding the "disabled" to their "roles" db field. 