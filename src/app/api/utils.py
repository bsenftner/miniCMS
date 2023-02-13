from fastapi.security import OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from fastapi import HTTPException
from fastapi import status
from typing import Optional
from typing import Dict

from datetime import datetime
from dateutil import tz

# ---------------------------------------------------------------------------------------
class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        # changed to accept access token from httpOnly Cookie:
        authorization: str = request.cookies.get("access_token")  
        # print("access_token is",authorization)

        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return param
    

# ---------------------------------------------------------------------------------------
def convertDateToLocal( date: datetime ) -> datetime:
    
    # fix date to be local time:
    from_zone = tz.tzutc()
    # to_zone = tz.tzlocal()
    to_zone = tz.gettz('America/Denver')    # make user's local timezone
    utc_dt = date.replace(tzinfo=from_zone)
    local_dt = utc_dt.astimezone(to_zone)
    
    return local_dt
