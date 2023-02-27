from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    ForeignKey,
    MetaData,
    String,
    Table,
    create_engine
)
from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from databases import Database

from app.config import get_settings

from functools import lru_cache

import sqlalchemy # only for the __version__ expression below

# ----------------------------------------------------------------------------------------------
class DatabaseMgr:
    def __init__(self):
        # SQLAlchemy
        print(sqlalchemy.__version__)
        url = get_settings().DATABASE_URL
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        #
        self.engine = create_engine(url) # , future=True) adding the future parameter enables SQLAlchemy 2.0 syntax

        # metadata is a container for tables
        self.metadata = MetaData()

        self.users_tb = Table(
            "users",
            self.metadata,
            Column("userid", Integer, primary_key=True, autoincrement="auto"),
            Column("username", String, index=True, unique=True, nullable=False),
            Column("hashed_password", String(80), nullable=False),
            Column("email", String(80), index=True, unique=True, nullable=False),
            Column("roles", String),
            Column("verify_code", String(16)),
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )
        
        self.memo_tb = Table(
            "memo",
            self.metadata,
            Column("memoid", Integer, primary_key=True, index=True),
            Column("userid", Integer, ForeignKey("users.userid")),
            Column("username", String, ForeignKey("users.username")),
            Column("projectid", Integer, ForeignKey("project.projectid")),
            Column("title", String),
            Column("text", String),
            Column("status", String, default="unpublished"),
            Column("access", String),
            Column("tags", String),
            Column("created_date", DateTime, default=func.now(), nullable=False),
            Column("updated_date", DateTime, default=func.now(), onupdate=func.now(), nullable=False),
            
        )
        
        self.comment_tb = Table(
            "comment",
            self.metadata,
            Column("commid", Integer, primary_key=True, index=True),
            Column("text", String),
            Column("memoid", Integer, ForeignKey("memo.memoid")),
            Column("userid", Integer, ForeignKey("users.userid")),
            Column("username", String, ForeignKey("users.username")),
            Column("parent", Integer, ForeignKey("comment.commid")),
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )
        
        # tags are used for multiple things. They act as unique identifiers, access fences, and search terms. 
        # User roles are soon to become tags. 
        # Project names become tags, with each memo associated with the project getting that project's tag. 
        # User roles act as access permissions, and users on a project receive a role of that project's name, which is also a tag. 
        self.tag_tb = Table(
            "tag",
            self.metadata,
            Column("tagid", Integer, primary_key=True, index=True),
            Column("text", String, index=True, unique=True, nullable=False),
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )
        
        self.project_tb = Table(
            "project",
            self.metadata,
            Column("projectid", Integer, primary_key=True, index=True), 
            Column("userid", Integer, ForeignKey("users.userid")),          # creator/owner of project 
            Column("username", String, ForeignKey("users.username")),       # same
            Column("name", String, index=True),                             # name of project, also becomes a tag with this name
            Column("text", String),                                         # project description
            Column("status", String, default="unpublished"),                # unpublished means not visible to staff
            Column("tagid", Integer, ForeignKey("tag.tagid")),              # tagid defining the access role for this project 
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )

        self.notes_tb = Table(
            "notes",
            self.metadata,
            Column("id", Integer, primary_key=True),
            Column("owner", Integer, index=True),
            Column("title", String, index=True),
            Column("description", String),      # describe the data here
            Column("data", String),             # data saved as string of encoded json
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )

        self.action_tb = Table(
            "action",
            self.metadata,
            Column("actionid", Integer, primary_key=True),
            Column("userid", Integer, ForeignKey("users.userid")),  # user who performed the action
            Column("actionLevel", Integer, index=True),         # UserActionLevel values, nature of what they did
            Column("actionCode", Integer, index=True),          # UserAction values, what they did
            Column("description", String),                      # additional info here
            Column("created_date", DateTime, default=func.now(), nullable=False),
        )
        
        # databases query builder
        self.database = Database(get_settings().DATABASE_URL)

        # create db tables if they don't already exist:
        self.metadata.create_all(self.engine)
        
    def get_db(self):
        return self.database
    
    def get_metadata(self):
        return self.metadata
        
    def get_users_table(self):
        return self.users_tb
        
    def get_memo_table(self):
        return self.memo_tb
        
    def get_comment_table(self):
        return self.comment_tb
        
    def get_tag_table(self):
        return self.tag_tb
        
    def get_project_table(self):
        return self.project_tb
        
    def get_notes_table(self):
        return self.notes_tb
        
    def get_action_table(self):
        return self.action_tb


# ----------------------------------------------------------------------------------------------
@lru_cache()
def get_database_mgr() -> DatabaseMgr:
    database_mgr = DatabaseMgr()
    return database_mgr




