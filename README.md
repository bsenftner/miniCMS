# A FastAPI based multi-user CMS / DMS experiment (content management & document management)

## Very much a work in progress at this point, informally declared version 0.9

Features in place so far:

- Duel local and prod docker compose setups
  - FastAPI, Postgresql, SQLAlchemy, Pydantic, Databases
- User accounts
  - roles (admin/staff)
  - email verification
  - Settings page for account mgmnt
    - password and email change
    - admins get a few more settings:
      - Generate and download a site database backup
      - Review site users, their account settings, projects and roles
  - End-user profile pages for end-webmaster to put a GUI for whatever is the purpose behind their using MiniCMS
- 'Project' content type
  - A collection of files, memo and comments only accessible by Project members
  - A Project overview page for description, members, and project files
  - Project editor uses an embedded rich text editor (TinyMCE)
  - Intended to serve as the secure collection point for project information between members potentially in different locations
- 'Memo' content type
  - Memos are containers for each project's text, image, video, PDF and related info and files
  - Any project information needed by different members should be in a project memo
    - including info for recreating the project later
  - Both Memo and Comment editor use an embedded rich text editor (TinyMCE)
  - title, content text, file uploads, upload embedding, status, access, and tags
    - files may be uploaded
      - which become available as embed links and download buttons
        - image, video and pdf embeds are working
      - All uploads go into a Project specific directory
    - status can be unpublished or published
      - once published, a memo can no longer be edited by non-admin project members
      - admins can see and edit unpublished and published memos of others
    - configuring access is different between admin and staff
      - admins can set access to: admin, staff, or public
        - admin access is only visible to other admins
        - staff access is visible to admin and staff
        - public access is visible to the public, and staff, but only admins can create public memos
          - I am considering removing public access memos
      - staff can only create staff visible memos, so the access controls disappear when a user with only the staff role is editing
- 'Comment' content type
  - for commenting on memos
    - access to a Comment is controlled by the memo it is associated
  - uses a reduced functionality embed of TinyMCE editor, but still allows image, video and pdf embeds
  - comments, once posted, cannot be edited
  - support for nested comments is in place, just not completed yet
- 'Tag' content type
  - for unique term management, employed for multiple uses
    - "system tags" are used for
      - "status" (unpublished, published, archived)
      - access permissions (admin, staff, public)
    - Project names each become a tag, defining an access role for that Project
      - this is probably going to become a separate project tag, so the project name can be unrestricted
- 'Note' content type
  - Intended for programmatic usage
  - has title, description, and data (JSON) fields
  - currently only used for site's configuration
  - notes do not have a web page GUI for editing them (yet)

Account roles are track admin/staff and unverified (email) statuses, they also hold project memberships.
Pproject memberships are honored by memos, meaning users not members of a project cannot load its memos.

This is a fork of my other repo FastAPI_TDD_Docker, focusing on a more formal CMS experience (without going to far.)
From that other repo are tests, yet to be updated to this repo, untested backups, and a Traefik https config for prod.
Soon those will get attention.

![webpage screen shot](/src/app/static/MiniCMS-project.jpg)

A Project page showing the project description (top), members, uploaded files, and memo links

![webpage screen shot](/src/app/static/MiniCMS-richEditor.jpg)

A detail on the rich text editor, with the usual expected rich editing widgets, plus image, video embed controls

![webpage screen shot](/src/app/static/MiniCMS-memo.jpg)

A published memo, with the comment editor and upload file controls

![webpage screen shot](/src/app/static/MiniCMS-adminSettings.jpg)

The admin settings page. Each user's settings is similar, just fewer things for non-admins
