from fastapi import HTTPException, Depends, status, Request, BackgroundTasks

from app.config import get_settings, log
from app.api.models import UserInDB, UserReg
from app.api import encrypt, crud
#
# from fastapi.security import OAuth2PasswordBearer
from app.api.utils import OAuth2PasswordBearerWithCookie

from email_validator import validate_email, EmailNotValidError
from app.send_email import send_email_async

from jose import JWTError, jwt
from typing import Any, Union
from datetime import datetime, timedelta

from enum import IntEnum

# add OAuth2, declaring the url to get user auth tokens:
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scheme_name="JWT")
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="token", scheme_name="JWT")


# -------------------------------------------------------------------------------------
async def get_user(username: str) -> UserInDB:
    # log.info(f"get_user: looking for {username}")
    user = await crud.get_user_by_name(username)
    if not user:
        log.info(f"get_user: no such user")
        return False
    
    username = user['username']
    userid = user['userid']
    verify_code = user["verify_code"]
    hashed_password = user["hashed_password"]
    email = user["email"]
    roles = user["roles"]

    return UserInDB(username=user["username"], 
                    userid=userid, 
                    verify_code=verify_code,
                    hashed_password=hashed_password,
                    email=email,
                    roles=roles)

# -------------------------------------------------------------------------------------
async def get_user_by_email(email: str) -> UserInDB:
    user = await crud.get_user_by_email(email)
    if not user:
        log.info(f"get_user_by_email: no such user")
        return False
    return UserInDB(username=user["username"], 
                    userid=user["userid"], 
                    verify_code=user['verify_code'],
                    hashed_password=user["hashed_password"],
                    email=user["email"],
                    roles=user["roles"])


# -----------------------------------------------------------------------------------------
# only verifies the passed username and password match, does not check if user is disabled! 
async def authenticate_user_password(username: str, password: str):
    user = await get_user(username)
    if not user:
        return False
    if not encrypt.verify_password(password, user.hashed_password):
        return False
    return user


# -------------------------------------------------------------------------------------
def create_access_token(subject: Union[str, Any], expires_delta: int = None) -> str:
    
    settings = get_settings() # application config settings
    
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES)
    
    to_encode = {"exp": expires_delta, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
    return encoded_jwt

# -------------------------------------------------------------------------------------
def create_refresh_token(subject: Union[str, Any], expires_delta: int = None) -> str:
    
    settings = get_settings() # application config settings
    
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRES_MINUTES)
    
    to_encode = {"exp": expires_delta, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_REFRESH_KEY, settings.JWT_ALGORITHM)
    return encoded_jwt




# -------------------------------------------------------------------------------------
# the 'roles' user field is a string, expected to contain a series of space delimited 
# words. Each 'word' is one role that user has. In most cases a 'role' is like a     
# permission: the 'admin' role grants administrator access to the website. In contrast, 
# the 'unverified' role identifies that user as not yet having verified their email, and         
# because of that has limited capabilities. In another case, the 'staff' role is a   
# default role everyone gets, and at this time does not mean anything. 
# valid roles are:
#   staff       - everyone with an account   
#   unverified  - user has not verified their email yet 
#   admin       - user is administrator  
#   disabled    - user account is disabled, no longer allowed to login 
def user_initial_roles( isAdmin: bool ) -> str:
    ret = 'staff unverified'
    if isAdmin:
        ret += ' admin'
    ret += ' MiniCMS' # site documentation project
    return ret

# -------------------------------------------------------------------------------------
def user_has_role( user: UserInDB, role: str) -> bool:
    return role in user.roles

# -------------------------------------------------------------------------------------
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=302, # status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        # headers={"WWW-Authenticate": "Bearer"},
        headers={"Location": "/login"},
    )
    try:
        settings = get_settings() # application config settings
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        log.info(f"get_current_user: username is {username}")
        expTime: str = payload.get("exp")
        log.info(f"get_current_user: exp is {expTime}")
        if username is None:
            raise credentials_exception
        if expTime is None:
            raise credentials_exception
        
        if datetime.fromtimestamp(expTime) < datetime.now():
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
    except JWTError:
        raise credentials_exception
    
    user = await get_user(username) 
    if user is None:
        log.info("get_current_user: user is None!")
        raise credentials_exception
    return user


# -------------------------------------------------------------------------------------
async def get_refresh_user(request: Request) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        cookies = request.cookies # json.loads(request.cookies)
        settings = get_settings() # application config settings
        payload = jwt.decode(cookies['refresh_token'], settings.JWT_SECRET_REFRESH_KEY, algorithms=[settings.JWT_ALGORITHM]) 
        username: str = payload.get("sub")
        expTime: str = payload.get("exp")
        if username is None:
            raise credentials_exception
        if expTime is None:
            raise credentials_exception
        
        if datetime.fromtimestamp(expTime) < datetime.now():
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
            

    except JWTError:
        raise credentials_exception
    
    user = await get_user(username=username) # token_data.username)
    if user is None:
        raise credentials_exception
    return user


# -------------------------------------------------------------------------------------
async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if user_has_role(current_user, 'disabled'):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user




# -------------------------------------------------------------------------------------
async def validate_email_address(email: str):
    try:
        validation = validate_email( email, check_deliverability=True)
        # get Unicode normalized version of email address:
        email = validation.email
        
    except EmailNotValidError as e:
        return { "success": False, "msg": str(e) }
        
    return { "success": True, "msg": email }

# -------------------------------------------------------------------------------------
async def validate_new_user_info(user: UserReg):
    
    log.info(f'validate_new_user_info: got {user}')
    
    existingUser = await get_user(user.username)
    if existingUser:
        log.info('validate_new_user_info: exit 1')
        return { "success": False, 
                 "status_code": status.HTTP_409_CONFLICT, 
                 "msg": "Username already in use."
               }
    
    ret = await validate_email_address(user.email)
    if ret['success']:
        user.email = ret['msg']
    else:
        log.info('validate_new_user_info: exit 2')
        return { "success": False, 
                 "status_code": status.HTTP_406_NOT_ACCEPTABLE, 
                 "msg": ret['msg']
               }
    
    existingUser = await get_user_by_email(user.email)
    if existingUser:
        log.info('validate_new_user_info: exit 3')
        return { "success": False, 
                 "status_code": status.HTTP_409_CONFLICT, 
                 "msg": "Email already in use."
               }
    
    
    log.info('validate_new_user_info: exit 4 - the good one')
    return { "success": True, 
             "status_code": status.HTTP_200_OK, 
             "msg": user.email 
           }
    
    
# -------------------------------------------------------------------------------------
async def send_email_validation_email(username: str, 
                                      email: str, 
                                      verify_code: str, 
                                      background_tasks: BackgroundTasks):
    
    body = r'''<p>Hello {name}</p>
<p>Here is your email verification code:<\p>
<p>{code}<\p>
<p>You will be asked to enter this code upon your next login. 
Email verification enables posting and account changes.</p>
<p>-Admin</p>'''
    body = body.format(name=username, code=verify_code)

    params = { 'msg': { 'subject': 'Verification email',
                        'body': body }
             }
    # print(json.dumps(params, indent = 4))
    
    await send_email_async(email, params, 'verify_email.html', background_tasks)
    
       
# -------------------------------------------------------------------------------------
async def send_password_changed_email(username: str, email: str, new_password: str):
    
    body = r'''<p>Hello {name}</p>
<p>Your username at this website is:<\p>
<p>{name}<\p>
<p>Your password has recently changed and is now:<\p>
<p>{password}<\p>
<p>Use these to login to the website in the future. Note, this email is the only location this password is plaintext.</p>
<p>-Admin</p>'''
    body = body.format(name=username, password=new_password)

    params = { 'msg': { 'subject': 'Password changed email',
                        'body': body }
    }
    # print(json.dumps(params, indent = 4))
    await send_email_async(email, params, 'verify_email.html')
