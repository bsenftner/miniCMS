# A FastAPI based multi-user CMS experiment

## Very much a work in progress at this point, informally declared version 0.5

Features in place so far:

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
  - intended for company (and soon group) communications on a project
  - using TinyMCE editor
  - has title, content text, status, access, and tags
    - status can be unpublished or published
      - once published memo can no longer be edited by staff (admin can)
    - access can be admin, staff or public
      - soon to include project/group access as well
    - tags are not yet fully implmented, will be search term for similar memos
- 'Comment' content type
  - for commenting on memos
    - intent is more content types and Comments to be used on any of them
    - access to a Comment is controlled by the memo it is associated
  - uses a reduced functionality embed of TinyMCE editor
  - comments, once posted, cannot be edited
  - underly support for nested comments is in place, just not completed yet

Account roles are getting more formalized. Where they currently track admin/staff and unverified (email) statuses, they will also
hold project/group memberships. Those project/group memberships will also be honored by memos.

This is a fork of my other repo FastAPI_TDD_Docker, focusing on a more formal CMS experience (without going to far.)
From that other repo are tests, yet to be updated to this change, and untested backups. Soon those will get attention.

![webpage screen shot](/src/app/static/MiniCMS-memo.jpg)
