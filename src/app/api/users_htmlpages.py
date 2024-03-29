
from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, BackgroundTasks
from app.api.models import Token, UserInDB, UserPublic, UserReg, basicTextPayload, NoteDB
from app.api.users import get_current_active_user, user_has_role, validate_new_user_info
from app.api.user_action import UserAction, UserActionLevel
from app.api import encrypt 

from fastapi.security import OAuth2PasswordRequestForm

import secrets
import string

import json

from pydantic import EmailStr

from typing import List

from app.config import get_settings, log 
from app.api import crud, users 

# create a local API router for the endpoints created in this file:
router = APIRouter()


    
# -------------------------------------------------------------------------------------
@router.post("/token", summary="Create access and refresh tokens for user", response_model=Token)
async def login_for_access_token(response: Response, 
                                 form_data: OAuth2PasswordRequestForm = Depends()):

    user = await users.authenticate_user_password(form_data.username, form_data.password)
    if not user:
        """ can't do this without a violating the userid's foreign key constraint - no userid 0
        await crud.rememberUserAction( 0, # userid == 0 because we don't know who is doing this
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('BAD_USERNAME_OR_PASSWORD'), 
                                       f"attempted with {form_data.username} and {form_data.password}" ) """
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bad username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    #
    if users.user_has_role( user, 'disabled'):
        await crud.rememberUserAction( user.userid, 
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('DISABLED_USER_LOGIN_ATTEMPT'),
                                       f"attempted with {form_data.username}" )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Disabled user",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = users.create_access_token(form_data.username)
    
    access_cookie_value = f"Bearer {access_token}"
    
    refresh_token = users.create_refresh_token(form_data.username)
    
    refresh_cookie_value = refresh_token
    
    settings = get_settings() # application config settings
    
    # Store refresh and access tokens in cookie
    response.set_cookie('access_token', 
                        access_cookie_value, 
                        settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
                        settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60, 
                        '/', None, False, True, 'lax')
    response.set_cookie('refresh_token', 
                        refresh_cookie_value,
                        settings.REFRESH_TOKEN_EXPIRES_MINUTES * 60, 
                        settings.REFRESH_TOKEN_EXPIRES_MINUTES * 60, 
                        '/', None, False, True, 'lax')

    await crud.rememberUserAction( user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('CREATE_ACCESS_TOKEN'), "" )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


# --------------------------------------------------------------------------------------------------------------
# Refresh access token
@router.get('/refresh', summary="Submit refresh token and get new access token")
async def refresh_token(response: Response, request: Request): 
    try:
        refreshUser: UserInDB = await users.get_refresh_user(request)
        if not refreshUser:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                detail='The user belonging to this token no logger exist')

        username = refreshUser.username
        access_token = users.create_access_token(username)
        access_cookie_value = 'Bearer ' + access_token

        settings = get_settings() # application config settings
        
        # Store refresh and access tokens in cookie
        response.set_cookie('access_token', 
                        access_cookie_value, 
                        settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
                        settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60, 
                        '/', None, False, True, 'lax')
        
        await crud.rememberUserAction( refreshUser.userid, 
                                       UserActionLevel.index('NORMAL'),  
                                       UserAction.index('REFRESHED_ACCESS_TOKEN'), "" )
    
    except Exception as e:
        error = e.__class__.__name__
        if error == 'MissingTokenError':
            raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST, detail='Please provide refresh token')
        raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST, detail=error)
        
    return {'access_token': access_token}


# --------------------------------------------------------------------------------------------------------------
# return info about the current logged in user:
@router.get("/users/me", 
            status_code=status.HTTP_200_OK, 
            summary="Get current logged in user data", 
            response_model=UserPublic)
async def read_users_me(request: Request, 
                        current_user: UserInDB = Depends(users.get_current_active_user)):
    
    log.info(f'read_users_me: got {current_user}')
    
    # print(request.cookies)
    return {"username": current_user.username, 
            "userid": current_user.userid, 
            "email": current_user.email, 
            "roles": current_user.roles}

# --------------------------------------------------------------------------------------------------------------
# return list of current users:
@router.get("/users", 
            status_code=status.HTTP_200_OK, 
            summary="Get list of current users, admin use only", 
            response_model=List[UserPublic])
async def read_users(request: Request, 
                    current_user: UserInDB = Depends(users.get_current_active_user)) -> List[UserPublic]:
    
    log.info(f'read_users: got {current_user}')
    
    """ so staff can add/remove people from their own projects, commented out that is
    if not users.user_has_role( current_user, 'admin' ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('NONADMIN_REQUESTED_USER_LIST'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access User list") """
    
    userList = await crud.get_all_users()
    
    log.info(f'read_users: returning userList {userList}')
    
    return userList

# --------------------------------------------------------------------------------------------------------------
# return list of project users:
@router.get("/users/{projectTag}", 
            status_code=status.HTTP_200_OK, 
            summary="Get list of Project users given the Project Tag, admin use only", 
            response_model=List[UserPublic])
async def read_project_users(request: Request, 
                     projectTag: str,
                     current_user: UserInDB = Depends(users.get_current_active_user)) -> List[UserPublic]:
    
    log.info(f'read_project_users: got {current_user}')
    
    """ 
    if not users.user_has_role( current_user, 'admin' ) and not users.user_has_role( current_user, projectTag ):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('NONMEMBER_ATTEMPTED_GET_PROJECT_MEMBERS'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to access Project User list") """
    
    userList = await crud.get_all_users_by_role(projectTag)
    
    return userList


# --------------------------------------------------------------------------------------------------------------
@router.post("/users/register",  
             status_code=status.HTTP_201_CREATED, 
             summary="Register new user", 
             response_model=UserPublic)
async def sign_up(user: UserReg, background_tasks: BackgroundTasks):
    
    log.info(f'sign_up: got {user}')
    
    site_config: NoteDB = await crud.get_note(1) # site_config has id 1
    if site_config:
        site_config.data = json.loads(site_config.data)
        # config.log.info(f"register: site_config.data is {site_config.data}")
        if site_config.data['public_registration'] == False:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                detail="Public registration is unauthorized")
    
    ret = await validate_new_user_info(user)
    # log.info(f"sign_up: ret is {ret}")
    #
    success = ret["success"]
    status_code = ret["status_code"]
    msg = ret["msg"]
    #
    """ log.info(f"sign_up: ret.success is {success}")
    log.info(f"sign_up: ret.status_code is {status_code}")
    log.info(f"sign_up: ret.msg is {msg}") """
    
    if not success:
        raise HTTPException( status_code=status_code, 
                             detail=msg, 
                             headers={"WWW-Authenticate": "Bearer"}, )
    
    # when successful, validate_new_user_info() returns the Unicode normalized email in the msg return field:
    emailAddr = EmailStr(msg)
    
    settings = get_settings() # application config settings
    
    isAdmin = False
    # in app config the username and email of the admin/superuser is kept:
    if user.username==settings.ADMIN_USERNAME and user.email==settings.ADMIN_EMAIL:
        isAdmin = True
    #
    roles = users.user_initial_roles( isAdmin ) # returns the initial roles granted to a new user
        
    # we store the hashed password in the db:
    hashed_password = encrypt.get_password_hash(user.password)
    
    # generate an email verification code:
    verify_code = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(16))
    # log.info(f'email verification code is {verify_code}')
        
    # validation of user info complete, create the user in the db:
    last_record_id = await crud.post_user( user, hashed_password, verify_code, roles )
    
    await crud.rememberUserAction( last_record_id, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('CREATED_NEW_USER'), 
                                   f"name {user.username}" )
    
    await users.send_email_validation_email( user.username, user.email, verify_code, background_tasks )
    
    return {"username": user.username, "userid": last_record_id, "email": emailAddr, "roles": roles}


# --------------------------------------------------------------------------------------------------------------
@router.post("/users/create",  
             status_code=status.HTTP_201_CREATED, 
             summary="Admin create new user", 
             response_model=UserPublic)
async def sign_up(payload: UserReg, 
                  background_tasks: BackgroundTasks,
                  current_user: UserInDB = Depends(users.get_current_active_user)):
    
    log.info(f'sign_up: got {payload}')
    
    if not user_has_role(current_user, " admin"):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('NONADMIN_REQUESTED_CREATE_NEW_USER'), 
                                       "Not Authorized" )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Not Authorized to create new user account")
    
    ret = await validate_new_user_info(payload)
    log.info(f"sign_up: ret is {ret}")
    #
    success = ret["success"]
    status_code = ret["status_code"]
    msg = ret["msg"]
    #
    """ log.info(f"sign_up: ret.success is {success}")
    log.info(f"sign_up: ret.status_code is {status_code}")
    log.info(f"sign_up: ret.msg is {msg}") """
    
    if not success:        
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('BAD_CREATE_NEW_USER_DATA'), 
                                       f"msg: {msg}" )
        raise HTTPException( status_code=status_code, 
                             detail=msg, 
                             headers={"WWW-Authenticate": "Bearer"}, )
    
    # when successful, validate_new_user_info() returns the Unicode normalized email in the msg return field:
    emailAddr = EmailStr(msg)
    
    settings = get_settings() # application config settings
    
    isAdmin = False
    roles = users.user_initial_roles( isAdmin ) # returns the initial roles granted to a new user
        
    # we store the hashed password in the db:
    hashed_password = encrypt.get_password_hash(payload.password)
    
    # generate an email verification code:
    verify_code = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(16))
    log.info(f'email verification code is {verify_code}')
        
    # validation of user info complete, create the user in the db:
    last_record_id = await crud.post_user( payload, hashed_password, verify_code, roles )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('CREATED_NEW_USER'), 
                                   f"admin {current_user.username} created new user named {payload.username}" )
    
    await users.send_email_validation_email( payload.username, payload.email, verify_code, background_tasks )
    
    return {"username": payload.username, "userid": last_record_id, "email": emailAddr, "roles": roles}

# --------------------------------------------------------------------------------------------------------------
@router.post("/users/logout",  
             status_code=status.HTTP_200_OK, 
             summary="Logout current user", 
             response_model=UserPublic)
async def logout(response: Response, current_user: UserInDB = Depends(users.get_current_active_user)):
    
    response.set_cookie(key="access_token",value=f"Bearer 0", httponly=True)
    response.set_cookie(key="refresh_token",value=f"0", httponly=True)
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('USER_LOGOUT'), "" )
    
    return {"username": current_user.username, 
            "userid": current_user.userid, 
            "email": current_user.email, 
            "roles": current_user.roles}


# -------------------------------------------------------------------------------------
@router.post("/users/verify",  
             status_code=status.HTTP_200_OK, 
             summary="Accept user email verification code")
async def verify_user_email(payload: basicTextPayload, current_user: UserInDB = Depends(users.get_current_active_user)):

    statusStr = "Already verified"
    
    if users.user_has_role( current_user, 'unverified'):
        log.info(f"current_user vcode {current_user.verify_code} and payload vcode {payload.text}")
        if current_user.verify_code != payload.text:
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('CONFUSED'),
                                           UserAction.index('FAILED_EMAIL_VERIFY'), "" )
            raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="The verification code does not match.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        else:
            # from here till the line break is removing 'unverified' from roles: 
            role_list = current_user.roles.split()
            current_user.roles = ''
            first = True
            for role in role_list:
                if role != 'unverified':
                    if not first:
                        current_user.roles += ' '
                    current_user.roles += role
                    first = False
            
            # update user in the database: 
            id = await crud.put_user( current_user.userid, current_user )
            if id != current_user.userid:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('NORMAL'),
                                           UserAction.index('VERIFIED_EMAIL'), "" )
            statusStr = "Ok"
            
    return { 'status': statusStr }


# -------------------------------------------------------------------------------------
# accepts username or a user's email, resets their password and sends email with new password 
# specifically not a protected endpoint. 
@router.post("/users/resetpass",  
             status_code=status.HTTP_200_OK, 
             summary="Reset password and send user email with new password")
async def reset_user_password(payload: basicTextPayload):

    log.info(f"reset_user_password: working with >{payload.text}<")
    
    existingUser: UserInDB = await users.get_user(payload.text)
    if not existingUser:
        existingUser: UserInDB = await users.get_user_by_email(payload.text)
        if not existingUser:
            await crud.rememberUserAction( 0, 
                                           UserActionLevel.index('WARNING'),
                                           UserAction.index('UNKNOWN_USER_RESET_PASSWORD_ATTEMPT'), 
                                           f"tried with {payload.text}" )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user with that username or email found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            log.info('existing user was email')
    else:
        log.info('existing user was username')
    
    if users.user_has_role( existingUser, 'unverified'):
        await crud.rememberUserAction( existingUser.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('UNVERIFIED_USER_PASSWORD_RESET_ATTEMPT'), 
                                       f"name {existingUser.username}" )
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The requested account must have a verified email to receive reset passwords.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    reset_password = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(16))
    log.info(f'reset_password is {reset_password}')
    
    existingUser.hashed_password = encrypt.get_password_hash(reset_password)
    
    # update user in the database: 
    id = await crud.put_user( existingUser.userid, existingUser )
    if id!=existingUser.userid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    await crud.rememberUserAction( existingUser.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('USER_RESET_PASSWORD'), 
                                   f"name {existingUser.username}" )
    
    await users.send_password_changed_email(existingUser.username, existingUser.email, reset_password)
    
    return { 'status': 'ok' }


# -----------------------------------------------------------------------------------------------
# expects payload to be new roles setting for user with userid, admins and own user account only 
@router.post("/users/roles/{userid}",  
             status_code=status.HTTP_200_OK, 
             summary="sets a user's roles, admins only")
async def set_user_roles(userid: int, 
                         payload: basicTextPayload,
                         current_user: UserInDB = Depends(get_current_active_user)):

    log.info(f"set_user_roles: working with userid {userid} and payload >{payload.text}<")
    
    isAdmin = True
    if not user_has_role(current_user, " admin"):
        # user is not an admin:
        if userid == current_user.userid:
            isAdmin = False
        else:
            await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('BANNED_ACTION'),
                                       UserAction.index('NONADMIN_ATTEMPTED_USER_ROLES_ASSIGNMENT'), 
                                       f"tried to give userid {userid} roles: {payload.text}" )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to modify users")
    
    existingUser = await crud.get_user_by_id(userid)
    if not existingUser:
        raise HTTPException( status_code=status.HTTP_404_NOT_FOUND, detail="User not found", headers={"WWW-Authenticate": "Bearer"}, )
        
    if existingUser.userid==1:
        # don't allow admin role to be taken away from superuser 
        if not " admin" in payload.text:
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('BANNED_ACTION'),
                                           UserAction.index('NONADMIN_ATTEMPTED_USER_ROLES_ASSIGNMENT'), 
                                           f"tried to give userid {userid} non-admin roles: {payload.text}" )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to remove admin from superuser")
    
    if not isAdmin:
        # don't allow nonAdmins to make themselves admin: 
        # (if not an admin, can only be their own account)
        if " admin" in payload.text:
            await crud.rememberUserAction( current_user.userid, 
                                           UserActionLevel.index('BANNED_ACTION'),
                                           UserAction.index('NONADMIN_ATTEMPTED_USER_ROLES_ASSIGNMENT'), 
                                           f"tried to give userid {userid} admin roles: {payload.text}" )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized to make admin")
    
    log.info(f"set_user_roles: user: {existingUser.username}, {existingUser.userid}")
    
    first = True
    final = ""
    roles = payload.text.split()
    for role in roles:
        if not role in final:
            if first:
                first = False
            else:
                final += " "
            final += role
            
    old_roles = existingUser.roles
    existingUser.roles = final
    
    # update user in the database: 
    id = await crud.put_user( existingUser.userid, existingUser )
    if id!=existingUser.userid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('USER_ROLES_ASSIGNMENT'), 
                                   f"user {existingUser.userid} old roles: {old_roles}, new roles {existingUser.roles}" )
    
    return { 'status': 'ok' }

# -------------------------------------------------------------------------------------
@router.post("/users/setpass",  
             status_code=status.HTTP_200_OK, 
             summary="Set user password and send user email with new password")
async def set_user_password( payload: basicTextPayload, 
                             current_user: UserInDB = Depends(users.get_current_active_user)):
    
    if users.user_has_role( current_user, 'unverified'):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('UNVERIFIED_USER_SET_PASSWORD_ATTEMPT'), "" )
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Account must have a verified email to accept account changes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    current_user.hashed_password = encrypt.get_password_hash(payload.text)
    
    log.info(f'set_user_password: new hashed_password is {current_user.hashed_password}')
    
    # update user in the database: 
    id = await crud.put_user( current_user.userid, current_user )
    if id!=current_user.userid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('USER_SET_PASSWORD'), "" )
     
    await users.send_password_changed_email(current_user.username, current_user.email, payload.text)
    
    return { 'status': 'ok' }

# -------------------------------------------------------------------------------------
@router.post("/users/setemail",  
             status_code=status.HTTP_200_OK, 
             summary="Set user email and send email verification code to that account.")
async def set_user_email(payload: basicTextPayload, current_user: UserInDB = Depends(users.get_current_active_user)):
    
    if users.user_has_role( current_user, 'unverified'):
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('CONFUSED'),
                                       UserAction.index('UNVERIFIED_USER_SET_EMAIL_ATTEMPT'), "" )
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Account must have a verified email to accept account changes.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if payload.text == current_user.email:
        log.info('set_user_email: same email address, no change necessary.')
        return { 'status': 'ok' }
    
    ret = await users.validate_email_address(payload.text)
    # when successful, validate_email_address() returns the Unicode normalized email in a msg field:
    if ret['success']:
        current_user.email = EmailStr(ret['msg'])
    else:
        # when unsuccessful, validate_email_address() returns an error description in a msg field:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('WARNING'),
                                       UserAction.index('FAILED_USER_SET_EMAIL'), 
                                       ret['msg'] )
        raise HTTPException( status_code=status.HTTP_406_NOT_ACCEPTABLE, 
                              detail=ret['msg'], 
                              headers={"WWW-Authenticate": "Bearer"}, 
                            )
    
    # generate a new email verification code:
    current_user.verify_code = ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(16))
    
    # mark in user roles this user's email is unverified:
    current_user.roles = current_user.roles + ' unverified'
    
    # update user in the database: 
    id = await crud.put_user( current_user.userid, current_user )
    if id!=current_user.userid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('USER_SET_EMAIL'), 
                                   f"new email {current_user.email}" )
    
    await users.send_email_validation_email( current_user.username, current_user.email, current_user.verify_code )

    return { 'status': 'ok' }


# ----------------------------------------------------------------------------------------------
# Note: id's type is validated as greater than 0  
# Note: this disables the current logged in user's account, not someone else!
@router.delete("/users/disable", 
               status_code=status.HTTP_200_OK, 
               response_model=UserPublic, 
               summary="Disable the current user account.")
async def delete_user(current_user: UserInDB = Depends(users.get_current_active_user)):
    
    log.info( "delete_user: here!")
    
    # current_user is validated to be active, not disabled to get here, 
    # so its safe to directly disable:
    current_user.roles = current_user.roles + " disabled"
    id = await crud.put_user( current_user.userid, current_user )
    if id!=current_user.userid:
        await crud.rememberUserAction( current_user.userid, 
                                       UserActionLevel.index('SITEBUG'),
                                       UserAction.index('FAILED_DISABLE_USER'), 
                                       f"user {current_user.userid}, {current_user.username}" )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error.",
            headers={"WWW-Authenticate": "Bearer"})
    
    await crud.rememberUserAction( current_user.userid, 
                                   UserActionLevel.index('NORMAL'),
                                   UserAction.index('DISABLE_USER'), "" )
    
    return  {"username": current_user.username, 
             "userid": current_user.userid, 
             "email": current_user.email, 
             "roles": current_user.roles}
