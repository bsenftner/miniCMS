from typing import Union
from pydantic import BaseModel, Field, EmailStr, constr
from datetime import datetime

# create a "Pydantic Model" of the data we want to maintain in the database
# by inheriting from BaseModel. This inherits data parsing and validation 
# such that fields of the model are guaranteed to be these types when filled 
# with payloads for creating and updating things.

# here is a "note": something with a title, a description, and data 
class NoteSchema(BaseModel):
    title: str
    description: str
    data: str

# A "Note" in the database is simply an id plus our NoteSchema: 
class NoteDB(NoteSchema):
    id: int = Field(index=True)
    owner: int



# a "memo" is a post that appears to other site members when they login;
# the access field is used to restrict who sees the memo, 
# the access field holds csv roles, where a "role" is an attribute on a user. 
class MemoSchema(BaseModel):
    title: str
    text: str
    status: str
    tags: str 
    access: str 
    userid: int
    username: str 
    projectid: int  # parent/owner of memo, all memos belong to a project
 
class MemoDB(MemoSchema):
    memoid: int = Field(index=True)
    created_date: datetime
    updated_date: datetime
    
class MemoResponse(BaseModel):
    memoid: int
    

# a file uploaded for a project 
# who uploads this is inferred by the current_user when uploading
class ProjectFileCreate(BaseModel):
    filename: str = Field(index=True)  # uploaded filename+extension only, not full path, that's calc'ed from project
    projectid: int = Field(index=True) # project this file is associated
    
class ProjectFileDB(ProjectFileCreate):
    pfid: int = Field(index=True)
    userid: int                        # user who uploaded file
    version: int                       # highest value is the most current file version
    checked_userid: Union[int,None]    # if not None, file is checked out by Project Member
    checked_date: Union[datetime,None] # if not None, when file was checked out by checked_userid
    created_date: datetime


# a comment is a additional note added to a Memo, visible beneath a published Memo 
# Comments cannot be deleted or edited, but that is not controlled or important here;
#
# CommentSchema is used to create new comments
class CommentSchema(BaseModel):
    text: str
    memoid: int 
    userid: int 
    username: str 
    parent: Union[int,None] 
#
# a mirror is the db entry for a comment 
class CommentDB(BaseModel):
    text: str
    commid: int = Field(index=True)
    memoid: int = Field(..., foreign_key="MemoDB.memoid")
    userid: int = Field(...,foreign_key="UserInDB.userid")
    username: str = Field(..., foreign_key="UserInDB.userid")
    parent: Union[int,None] = Field(default=None, foreign_key="CommentDB.commid")
    created_date: datetime
#
# Comment creations return this:
class CommentResponse(BaseModel):
    commid: int
    


# an AiChat is a Project related Project Member conversation with an OpenAI AI. 
# Each begins with an AiChatCreate used to sent the end-user prompt/question to the AI, 
# The prePrompt field holds conversation context. The prompt field holds the latest   
# end-user question, and reply holds the most recent AI response. 
#
# AiChatCreate is used to create new comments
class AiChatCreate(BaseModel):
    prePrompt: str
    prompt: str
    reply: str
    model: str
    projectid: int
#
# a mirror of the db entry for an AIChat exchange 
class AiChatDB(BaseModel):
    prePrompt: str
    prompt: str
    reply: str
    model: str
    aichatid: int = Field(index=True)
    projectid: int = Field(..., foreign_key="ProjectDB.projectid")
    userid: int = Field(...,foreign_key="UserInDB.userid")
    username: str = Field(..., foreign_key="UserInDB.userid")
    created_date: datetime
    updated_date: datetime
#
# AiChatCreate requests return this when successful:
class AiChatCreateResponse(BaseModel):
    aichatid: int
    
    
    

class TagDB(BaseModel):
    tagid: int = Field(index=True)
    text: str = Field(index=True)


class ProjectRequest(BaseModel):
    name: str                                                   # project name
    text: str                                                   # project description
    tag: str                                                    # project tag
    
class ProjectUpdate(BaseModel):
    name: str                                                   # project name
    text: str                                                   # project description
    status: str                                                 # unpublished/published/archived
       
class ProjectSchema(BaseModel):
    name: str = Field(index=True)                               # project name
    text: str                                                   # project description
    userid: int = Field(...,foreign_key="UserInDB.userid")      # owner/creator
    username: str = Field(..., foreign_key="UserInDB.userid")
    status: str                                                 # unpublished/published/archived
    tagid: int = Field(..., index=True, foreign_key="TagDB.tagid") # tag id equal to our project tag

class ProjectDB(ProjectSchema):
    projectid: int = Field(index=True)
    created_date: datetime
    

# an access token used by authentication
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str
    
    
# a user 
class User(BaseModel):
    username: str
    email: EmailStr
    roles: str

# a user in the dabase
class UserInDB(User):
    userid: int = Field(index=True)
    verify_code: str
    hashed_password: str

# info for user registration
class UserReg(BaseModel):
    username: str
    password: constr(min_length=12)
    email: EmailStr
    
# info returned from a user query
class UserPublic(BaseModel):
    username: str
    userid: int
    roles: str
    email: EmailStr
    
 
# a user sending just a string:
class basicTextPayload(BaseModel):
    text: str
    


class UserActionCreate(BaseModel):
    actionLevel: int = Field(index=True)    # categorization of the action, severity level
    actionCode: int = Field(index=True)     # what happended, one of the UserAction enum values
    description: str                        # additional info about what happened
    

class UserActionDB(UserActionCreate):
    actionid: int = Field(index=True)
    userid: int = Field(index=True)     # who performed the action
    created_date: datetime
    
class UserActionResponse(BaseModel):
    action: str
    level: str
    username: str
    description: str
    created_date: str