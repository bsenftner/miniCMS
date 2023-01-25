from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    ForeignKey,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from databases import Database

from app.config import get_settings

from functools import lru_cache


# ----------------------------------------------------------------------------------------------
class DatabaseMgr:
    def __init__(self):
        # SQLAlchemy
        url = get_settings().DATABASE_URL
        # print(f"DatabaseMgr:__init__:: database_url = {url}")
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
            # print(f"DatabaseMgr:__init__:: tweaked database_url = {url}")
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
            Column("title", String),
            Column("description", String),
            Column("status", String, default="unpublished"),
            Column("access", String),
            Column("tags", String),
            Column("created_date", DateTime, default=func.now(), nullable=False),
            Column("updated_date", DateTime, default=func.now(), nullable=False),
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

        # databases query builder
        self.database = Database(get_settings().DATABASE_URL)

        # create db tables if they don't already exist:
        self.metadata.create_all(self.engine)
        
        
    def get_db(self):
        return self.database
        
    def get_users_table(self):
        return self.users_tb
        
    def get_memo_table(self):
        return self.memo_tb
        
    def get_comment_table(self):
        return self.comment_tb
        
    def get_notes_table(self):
        return self.notes_tb


# ----------------------------------------------------------------------------------------------
@lru_cache()
def get_database_mgr() -> DatabaseMgr:
    database_mgr = DatabaseMgr()
    return database_mgr




