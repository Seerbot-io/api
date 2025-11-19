from redis import Redis, ConnectionPool, SSLConnection, Connection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.cache import CACHE_TYPE, get_cache_type
from app.core.config import settings

class CacheRequestMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.pool = ConnectionPool(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT,
            socket_connect_timeout = 0.05,  # secs time to check connection
            socket_timeout=5,               # secs time to keep socket open
            retry_on_timeout = False,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            connection_class=SSLConnection if settings.REDIS_SSL else Connection  # SSLConnection for secure connection
            )

    async def dispatch(self, request: Request, call_next):
        method = request.method
        # turn all query path to lower case make it case insensitive -> do it in function too
        path = request.url.path.lower().strip()
        param = str(request.query_params if method == 'GET' else await request.body())
        cache_key = self.get_key(method, path, param)
        cache_type = get_cache_type(method, path)
        # print("====",param, method, path, cache_key, cache_type)

        # check cache
        if cache_type is not None:
            cache = self.get_cache_data(cache_key)
            if cache is not None:
                # print("Cache hit")
                return Response(
                    content=cache,
                    status_code=200,
                    # headers=dict(response.headers), 
                    media_type="application/json"
                    )
        # process request -> response
        try:
            response = await call_next(request)
        except Exception as e:
            print(e)
            response = Response(f"ERROR: Exception {str(type(e))}", status_code=500)
        # in case of error
        if response.status_code!=200:
            return response
        
        # set cache
        if cache_type is not None:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            # do not cache empty or short response
            if len(response_body) > 5 and self.set_cache_data(cache_key, response_body, cache_type):
                print("Cache set", path)
            else:
                print("Failed to set cache")
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers), 
                media_type= "application/json" if response.media_type is None else response.media_type
                )
        return response

    def redis_connect(self) -> Redis | None:
        rc = Redis(connection_pool=self.pool)
        try:
            if rc.ping():
                print("Connected to Redis")
                return rc
            else:
                print("Failed to connect to Redis")
                return None
        except Exception as e:
            print("Failed to connect to Redis", e)
            return None

    def get_key(self,method: str, path: str, param: str) -> str:
        """ get cache name with rule 
        """
        method = method.lower().strip()
        path = path.strip().strip('/')
        param = param.strip()
        # print(param)
        # key = self.context.hash(f"{method}:{path}:{param}")
        return f"{method}:{path}:{param}"

    def set_cache_data(self, cache_key:str, data: str, cache_type: str='in-5m') -> bool:
        # if method == 'GET': # process post body and get query , header, cookie, ... into cache name
        # todo: chose get string | dict | ...
        rc = self.redis_connect()
        if rc is None:  # failed to connect to redis
            return False
        rc.set(cache_key, data)
        if CACHE_TYPE[cache_type]['type'] == 'duration':
            rc.expire(cache_key, CACHE_TYPE[cache_type]['ttl'])
        elif CACHE_TYPE[cache_type]['type'] == 'at-time':
            rc.expireat(cache_key, CACHE_TYPE[cache_type]['ttl'])
        rc.close()
        return True
        
    def get_cache_data(self, cache_key: str) -> str | None:
        rc = self.redis_connect()
        if rc is None:  # failed to connect to redis
            return None
        # todo: chose set string | dict | ...
        result = rc.get(cache_key)
        rc.close()
        if result is not None and str(result).strip() != '':
            return result
        else:
            return None
