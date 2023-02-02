# A FastAPI based multi-user CMS / DMS experiment (content management & document management)

## Very much a work in progress at this point, informally declared version 0.6

Features in place so far:

- Duel local and prod docker compose setups
  - FastAPI, Postgresql, SQLAlchemy, Pydantic, Databases
- User accounts
  - roles (admin/staff)
  - email verification
  - Settings page for account mgmnt
    - password and email change
    - admins get a few more settings
  - End-user profile pages for end-webmaster to put a GUI for whatever is the purpose behind their using MiniCMS
- 'Note' content type
  - intended for programmatic usage
  - has title, description, and data (JSON) fields
  - currently only used for site's configuration
  - notes do not have a web page GUI for editing them (yet)
- 'Memo' content type
  - intended for company and group communications and document sharing on a project
  - using TinyMCE editor
  - has title, content text, file uploads, prior upload embedding, status, access, and tags
    - files may be uploaded
      - which become available as embed links and download buttons
        - image, video and pdf embeds are working
      - currently uploads all go to a central location
        - soon "projects" will be implemented that layer in another level of access control, with will impact uploads
          - where I am currently working
    - status can be unpublished or published
      - once published memo can no longer be edited by staff
      - admins can see and edit unpublished and published memos of others
    - configuring access is different between admin and staff
      - admins can set access to: admin, staff, or public
        - admin access is only visible to other admins
        - staff access is visible to admin and staff
        - public access is visible to the public, and staff, but only admins can create public memos
      - staff can only create staff visible memos, so the access controls disappear when a user with only the staff role is editing
      - soon to include project/group access as well
        - where I am currently working
    - tags are 90% implemented, working on their integration with related content types
- 'Comment' content type
  - for commenting on memos
    - intent is more content types and Comments to be used on any of them
    - access to a Comment is controlled by the memo it is associated
  - uses a reduced functionality embed of TinyMCE editor
  - comments, once posted, cannot be edited
  - support for nested comments is in place, just not completed yet
  - both memos and comments can have image, video and pdf embeds
- 'Tag' content type
  - for unique term management, employed for multiple uses
    - "system tags" are used for
      - "status" (unpublished, published, archived)
      - access permissions (admin, staff, public)
    - Projects will each have a tag, defining an access role for that Project
- 'Project' content type
  - for organization of memos, and access control of them and their documents
  - these are the container for a collection of memos concerning a single project
  - each project defines a "project tag"
    - that tag is an access role for any users on the project
    - that tag is automatically added to any memos associated with the project
  - also has a description field for an overview of the project

Account roles are getting more formalized. Where they currently track admin/staff and unverified (email) statuses, they will also
hold project/group memberships. Those project/group memberships will also be honored by memos.

This is a fork of my other repo FastAPI_TDD_Docker, focusing on a more formal CMS experience (without going to far.)
From that other repo are tests, yet to be updated to this repo, untested backups, and a Traefik https config for prod.
Soon those will get attention.

![webpage screen shot](/src/app/static/MiniCMS-memo.jpg)

General view of memo editing from a staff role account

![webpage screen shot](/src/app/static/MiniCMS-comments.jpg)

A published memo, with an embedded image and video, some comments, and the comment editor
