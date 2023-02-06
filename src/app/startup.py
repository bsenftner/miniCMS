import json   
from app.api.models import NoteSchema, MemoSchema, UserReg, basicTextPayload, TagDB, ProjectRequest
from app.api import crud, users, encrypt, project

from app.config import get_settings, log

import secrets
import string

# ---------------------------------------------------------------------------------------
# Called by app startup event, this ensures site_config exists in the db:
async def initialize_database_data( ) -> None:
    
    settings = get_settings() # application config settings
    
    # ensure initial user exists
    log.info("checking initial user exists...")
    adminUser = await crud.get_user_by_id(1)
    if not adminUser:
        log.info("creating first user...")
        
        first_user_payload = UserReg(username=settings.ADMIN_USERNAME, password=settings.ADMIN_PASSWORD, email=settings.ADMIN_EMAIL)
        roles = users.user_initial_roles( True ) # returns the initial roles granted to a new user
        hashed_password = encrypt.get_password_hash(first_user_payload.password)
        # generate an email verification code:
        verify_code = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(16))
        
        log.info(f"the admin email verification code is {verify_code}")
        log.info(f"posting first_user_payload...")
        
        # validation of user info complete, create the user in the db:
        last_record_id = await crud.post_user( first_user_payload, hashed_password, verify_code, roles )
        log.info(f"created first user with id {last_record_id}.")
        #
        adminUser = await crud.get_user_by_id(1)
    else:
        log.info(f"first username is '{adminUser.username}'")
        
        
    log.info('looking for site_config...')
    note = await crud.get_note_by_title('site_config')
    if not note:
        
        log.info('site_config not found, creating...')
        data = { "protect_contact": True }  # old, unused data; but there is no data for the webapp to maintain yet
        
        dataP = json.dumps(data) # dump to string
        
        note = NoteSchema(title="site_config",
                          description = "configuration data for admins",
                          data=dataP
                         )
        id = await crud.post_note( payload=note, owner=1)
        log.info(f"created site_config with id {id}.")
    
    else:
        log.info(f"Loaded site config: {note.data}")
        note.data = json.loads(note.data)
        log.info(f"site config recovered: {note.data}")
    
        
    # ensure initial tags used for system purposes exist:
    log.info("checking if system tags exist...")
    tag: TagDB = await crud.get_tag(1)
    if not tag:
        log.info("creating system tags...")
        tag_payload = basicTextPayload(text="unpublished")
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created first tag with id {id}.")
        #
        tag_payload.text = "published"
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created second tag with id {id}.")
        #
        tag_payload.text = "archived"
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created third tag with id {id}.")
    else:
        log.info(f"first tag is '{tag.text}'")
        tag: TagDB = await crud.get_tag(2)
        log.info(f"second tag is '{tag.text}'")
        tag: TagDB = await crud.get_tag(3)
        log.info(f"third tag is '{tag.text}'")
    #
    tag: TagDB = await crud.get_tag(4)
    if not tag:
        tag_payload = basicTextPayload(text="admin")
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created 4th tag with id {id}.")
        #
        tag_payload.text = "staff"
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created 5th tag with id {id}.")
        #
        tag_payload.text = "public"
        log.info(f"posting tag '{tag_payload}'...")
        id = await crud.post_tag(tag_payload)
        log.info(f"created 6th tag with id {id}.")
    else:
        log.info(f"4th tag is '{tag.text}'")
        tag: TagDB = await crud.get_tag(5)
        log.info(f"5th tag is '{tag.text}'")
        tag: TagDB = await crud.get_tag(6)
        log.info(f"6th tag is '{tag.text}'")
    
    # ensure initial project post exists
    log.info("checking if initial project exists...")
    proj = await crud.get_project(1)
    if not proj:
        log.info("creating first project...")
        first_project_payload = ProjectRequest(name="MiniCMS", 
                                               text="<p>Author of this software's notes</p>")
        log.info(f"posting {first_project_payload}...")
        projectid = await project.create_project(first_project_payload, adminUser)
        log.info(f"created first project with id {projectid}.")
    else:
        log.info(f"first project is '{proj.name}'")
        
    # ensure initial memo post exists
    log.info("checking if initial memo post exists...")
    memo = await crud.get_memo(1)
    if not memo:
        log.info("creating first memo...")
        first_memo_payload = MemoSchema(title="Hello Admins", 
                                        text="<p>What shall we do today?</p>", 
                                        status="unpublished", 
                                        access="admin", 
                                        tags="debug",
                                        userid=1, 
                                        username=settings.ADMIN_USERNAME,
                                        projectid=1)
        log.info(f"posting {first_memo_payload}...")
        id = await crud.post_memo(first_memo_payload,1)
        log.info(f"created first memo with id {id}.")
        
    else:
        log.info(f"first memo title is '{memo.title}'")
        



