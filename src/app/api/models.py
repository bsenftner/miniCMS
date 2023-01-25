from typing import Union
from pydantic import BaseModel, Field, EmailStr, constr

# create a "Pydantic Model" of the data we want to maintain in the database
# by inheriting from BaseModel. This inherits data parsing and validation 
# such that fields of the model are guaranteed to be these types when filled 
# with payloads for creating and updating things.

# here is a "note": something with a title, a description, and data 
class NoteSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=3, max_length=50)
    data: str

# A "Note" in the database is simply an id plus our NoteSchema: 
class NoteDB(NoteSchema):
    id: int
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
 
class MemoDB(MemoSchema):
    memoid: int = Field(index=True)

 
    
class CommentSchema(BaseModel):
    text: str
    memoid: int 
    userid: int 
    username: str 
    parent: Union[int,None] 
    
class CommentDB(BaseModel):
    text: str
    commid: int = Field(index=True)
    memoid: int = Field(..., foreign_key="MemoDB.memoid")
    userid: int = Field(...,foreign_key="UserInDB.userid")
    username: str = Field(..., foreign_key="UserInDB.userid")
    parent: Union[int,None] = Field(default=None, foreign_key="CommentDB.commid")


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
    # disabled: Union[bool, None] = None
    # email: Union[EmailStr, None] = None
    # roles: Union[str, None] = None

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
    # email: Union[EmailStr, None] = None
    
# info returned from a user query
class UserPublic(BaseModel):
    username: str
    userid: int
    roles: str
    email: EmailStr
    # roles: Union[str, None] = None
    # email: Union[EmailStr, None] = None
    
 
# a user sending just a string:
class basicTextPayload(BaseModel):
    text: str
    
