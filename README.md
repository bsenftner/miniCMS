# A FastAPI based multi-user CMS / DMS experiment (content management & document management)

## Version 1.1, in beta, looking for issues

### All required functionality is in place for secure project document & associated info management with remote located project members

![webpage screen shot](/src/app/static/AboutMiniCMS.jpg)

## Now ChatGPT Enabled: what the hell, I couldn't help myself... 

New page endpoints, available from a Project page:

  - /newAiExchange/[projectId]

and

  - /aiExchange/[aichatid]

converse with an "AI Attorney" I'm experimenting with; Looking into embedding CA legal case law knowledge

At the moment, the "AI Attorney" is good about being factual, not hallucinating facts or law, restricted to CA law

MiniCMS Features:

- Duel local and prod docker compose setups
  - FastAPI, Postgresql, SQLAlchemy, Pydantic, Databases
- User accounts
  - Roles (admin, staff, per-Project)
    - Basically operate as permissions; having a project role indicates project membership and access
  - Email verification
    - Until email verification, user account cannot do much, locked out of projects, which is almost everything
  - Settings page for account mgmnt
    - Password and email change
    - Admins get a few more settings:
      - Enable/disable public registration to website
      - Generate and download a site database backup
      - Review site users, their account settings, account roles, project memberships, and site use history
      - Create new user controls
  - End-user profile pages for end-webmaster to put a GUI for whatever is the purpose behind their using MiniCMS
- 'Project' content type
  - A collection of uploaded files, memos, comments and AI chats only accessible by Project members
    - See the uploaded files description in the Memo section
  - A Project overview page for description, members, and project files
  - Project Files are isolated, requiring Project membership and Project published status to access Project Files
  - Project editor uses an embedded rich text editor (TinyMCE)
  - Intended to serve as the secure collection point for project information between members potentially in different locations
  - Deleting a Project only deletes empty projects with no Memos or uploaded files
    - Attempts to delete a Project with uploaded files that are checked out for modification error
      - The checked out files must be checked in, or an Admin must cancel their checkout
    - Attempts to delete a Project with content is an archiving operation:
      - The Project itself and its Memos are marked as archived
      - Any files in the Project's upload directory are zip compressed
      - Project members are removed
      - Admins continue to see the Project, but as archived
- 'Memo' content type
  - Memos are containers for each project's text, image, video, PDF and related info and files
  - Any project information needed by different members should be in a project memo
    - including info for recreating the project later
  - Both Memo and Comment editor use an embedded rich text editor (TinyMCE)
  - title, content text, file uploads, upload embedding, status, access, and tags
    - files may be uploaded
      - which become available as embed links, 'checkout for modification' and download buttons
        - image, video and pdf embeds are working
      - Uploaded files have 'version control'
        - A Project Member is able to check out an uploaded file for modification
        - While 'checked out' other Project Memebers can download the uploaded last version of that file, but they cannot upload a modified version
          - It is clearly identified as 'locked for modification by username'
        - After the 'checked out member' finishes their changes, they can upload the new version
          - This will unlock the file for other Project Members to modify
          - Upon the modified file's upload, the file's version number increments and the older version is archived
      - All uploads go into an isolated Project directory requiring Project Membership to access
    - status can be unpublished, published or archived
      - once published, a memo can no longer be edited by non-admin project members
      - admins can see and edit unpublished and published memos of others
      - admins can see archived Projects and their memos and files, but they cannot be modified
    - configuring access is different between admin and staff
      - admins can set access to: admin, staff, or public
        - admin access is only visible to other admins
        - staff access is visible to admin and staff
        - public access is visible to the public, and staff, but only admins can create public memos
          - I am considering removing public access memos
            - The new Uploaded File security model makes any File embeds problematic
      - staff can only create staff visible memos, so the access controls disappear when a user with only the staff role is editing a memo
- 'Comment' content type
  - Control for commenting on memos
    - access to a Comment is controlled by the Memo and Project it is associated
  - Comments use a reduced functionality embed of TinyMCE editor, but still allows image, video and pdf embeds
  - Comments, once posted, cannot be edited
  - Support for nested comments is in place, just not completed yet, not sure if necessary
- 'AI Chat' content type
  - A chat interface to an AI knowledgable of CA Law and prompted to behave as an attorney
  - Current work has been functionality, and truthfullness, behaving as an attorney
  - Starting on carried conversational contexts
  - After that, embedding specific case law knowledge
- 'Tag' content type
  - for unique term management, employed for multiple uses
    - "system tags" are used for
      - "status" (unpublished, published, archived)
      - access permissions (admin, staff, public)
    - Projects each have a Project Tag, defining an access role for that Project
      - Project Tags are used as User Access Roles, as well as Project Memo search terms
- 'Note' content type
  - Intended for programmatic usage
  - has title, description, and data (JSON) fields
  - currently only used for site's configuration
  - notes do not have a web page GUI for editing them (yet)

Account roles are track admin/staff and unverified (email) statuses, they also hold project memberships.
Project memberships are honored by memos, meaning users not members of a project cannot load its memos.

This is a fork of my other repo FastAPI_TDD_Docker, focusing on a more formal CMS experience (without going to far.)
From that other repo are tests, yet to be updated to this repo, untested backups, and a Traefik https config for prod.
Soon those will get attention.

![webpage screen shot](/src/app/static/MiniCMS-project.jpg)

A Project page showing the project description (top), members, uploaded files, memo links, and the AI Attorney access

![webpage screen shot](/src/app/static/MiniCMS-aiAttorney.jpg)

The experimental AI Attorney page; it carries extened conversations with CA legal knowledge.

![webpage screen shot](/src/app/static/MiniCMS-richEditor.jpg)

A detail on the rich text editor, with the usual expected rich editing widgets, plus image, video embed controls

![webpage screen shot](/src/app/static/MiniCMS-memo.jpg)

A published memo, with the comment editor and upload file controls

![webpage screen shot](/src/app/static/MiniCMS-adminSettings.jpg)

The admin settings page. Each user's settings is similar, just fewer things for non-admins
