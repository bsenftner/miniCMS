import json   
from app.api.models import NoteSchema, MemoSchema, UserReg, basicTextPayload, TagDB, ProjectRequest
from app.api import crud, users, encrypt, project
from app.api.upload import check_project_uploads_for_orphans

from app.config import get_settings, log

import asyncio
from app.api.aichat import asyncio_fifo_worker

import secrets
import string


def docsHtml() -> str:
    ret = '''<h2>Welcome to MiniCMS Documentation</h2>
<h3>The Basics</h3>
<p><strong>MiniCMS</strong> is a project organized document and related memo managment system for secure in-office and remote work use.</p>
<p>As a <strong>Staff</strong> user you can see a listing of any <strong>Projects</strong> you are a member by clicking on the <strong>Profile Button</strong> located on the upper right of most <strong>MiniCMS</strong> pages. <br>Once on your <strong>Profile</strong> page you will see a listing of the <strong>Projects</strong> you are a member, just click their titles to enter the <strong>Project.</strong></p>
<p>A <strong>Project</strong> is a few things:</p>
<ul>
<li>A <strong>Project</strong> is a collection of people, the <strong>Project Members</strong>, collected for a purpose outside of <strong>MiniCMS</strong></li>
<li>A <strong>Project</strong> has a statement of purpose, presented when first loading the <strong>Project</strong> page, which is simply a <em>description</em> of the project
<ul>
<li>Your role as a member of the <strong>Project</strong> should be apparent from the <strong>Project</strong> description</li>
</ul>
</li>
<li>A <strong>Project</strong> has <strong>Uploaded Files</strong> related and for the purpose of the <strong>Project</strong> that are shared between <strong>Project Members</strong>
<ul>
<li>For example, one may have a <strong>Project </strong>that collects <strong>files </strong>related to a client matter. By placing the <strong>files </strong>into the <strong>Project </strong>they become available anywhere you can access <strong>MiniCMS</strong>.</li>
</ul>
</li>
<li>A <strong>Project</strong> has <strong>Memos</strong> that are notes written between <strong>Project Members</strong> related to the <strong>Project</strong> which need to be retained</li>
</ul>
<p><strong>Project</strong> is something people are trying to accomplish as a team. <strong>MiniCMS</strong> provides a way of organizing and sharing the files and information of the <strong>Project</strong> between in-office and remote workers without triggering expensive cloud file sharing fees imposed on businesses.</p>
<p>See the <strong><a href="/memoPage/1">About Project Memos</a> Memo</strong> for more site documentation.</p>'''
    return ret

def memoHtml() -> str:
    ret = '''<p>A <strong>Memo</strong> is some information related to a <strong>Project</strong> that ought to be maintained and kept with the <strong>Project</strong>.</p>
<p style="text-align: center;"><img src="/upload/projectFile/1/MiniCMS-memoEditor.jpg" alt="" width="800" height="116"><br><span style="font-size: 12pt;"><span style="font-size: 10pt;">
The <strong>Memo Editor</strong></span><span style="font-size: 10pt;"> is a <em>rich text editor</em></span><span style="font-size: 10pt;"> with many of the same controls as MS Word</span></span></p>
<p>If a <strong>Project</strong> is used to organize some client issue, a <strong>Memo</strong> is a good place to jot down client phone conversations. 
Likewise, with multiple member <strong>Projects</strong>, a <strong>Memo</strong> is a good method of communicating info and new developments of the <strong>Project</strong> 
between members with a date record of the communication.</p>
<p>Note that a <strong>Memo</strong> may include <em>embeds</em> of <strong>Project Uploaded Files</strong>. This enables <strong>Project Members</strong> to use 
<strong>Memos</strong> for <em>rich media</em> communications about a <strong>Project</strong>. When a <strong>Project Uploaded File<em> </em></strong>is a common 
image or video format the <strong>Uploaded File</strong> is presented in the <strong>Project Files</strong> section of the <strong>Memo Editor Page</strong> with a 
<strong>Copy Link (for embedding)</strong> button. Clicking the <strong>Copy Link (for embedding)</strong> button places the embed code for that 
<strong>Uploaded File</strong> onto your computer's <strong>clipboard</strong>. Then:</p>
<ul>
<li>If the <strong>Uploaded File</strong> is an <strong>image:</strong> clicking the <strong>Insert/edit image</strong> icon on the <strong>text editor toolbar</strong> 
pops a dialog the <strong>clipboard's embed code</strong> can be pasted to <strong>embed</strong> the <strong>image</strong> at the text editor's cursor location</li>
<li>If the <strong>Upload File</strong> is a <strong>video</strong>: clicking the <strong>Insert/edit media</strong> icon on the <strong>text editor toolbar</strong> 
pops a dialog the <strong>clipboard's embed code</strong> can be pasted to <strong>embed</strong> the <strong>video </strong>at the text editor's cursor location</li>
<li>If the <strong>Upload File</strong> is a <strong>PDF</strong>: clicking the <strong>Embed at cursor</strong> button <strong>embeds</strong> the <strong>PDF</strong> 
at the text editor's cursor location</li>
</ul>
<p>Once embedded into the <strong>Memo</strong> an <strong>image</strong> will display, a <strong>video</strong> appears with playback controls, and a <strong>PDF</strong> 
appears with the suite of expected <strong>PDF controls</strong>. Of course, these embedded files may be surrounded by explainer text as necessary to progress towards 
the goals of the <strong>Project</strong>.</p>'''
    return ret



        
        
# ---------------------------------------------------------------------------------------
# Called by app startup event, this ensures site_config exists in the db:
async def initialize_database_data( app ) -> None:
    
    settings = get_settings() # application config settings 
    
    
    asyncio.create_task( asyncio_fifo_worker() )  # for handling long running I/O API calls 
    
        
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
        data = { "public_registration": True }  # expose the registration page to the public, allow public registration to site
        
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
        first_project_payload = ProjectRequest(name="MiniCMS docs", 
                                               text=docsHtml(),
                                               tag="MiniCMS")
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
        first_memo_payload = MemoSchema(title="About Project Memos", 
                                        text=memoHtml(), 
                                        status="published", 
                                        access="staff", 
                                        tags="MiniCMS",
                                        userid=1, 
                                        username=settings.ADMIN_USERNAME,
                                        projectid=1)
        log.info(f"posting {first_memo_payload}...")
        id = await crud.post_memo(first_memo_payload,1)
        log.info(f"created first memo with id {id}.")
        
    else:
        log.info(f"first memo title is '{memo.title}'")
    
    # look for orphaned files and directories in the project upload area:
    await check_project_uploads_for_orphans( adminUser )
        



