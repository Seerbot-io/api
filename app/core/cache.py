# redis caching manager system 
import regex as re
from fastapi import APIRouter
from redis import ConnectionPool, SSLConnection
from datetime import datetime, timedelta


def at_every_n_min(minutes: int) -> int:
    time = datetime.now() + timedelta(minutes=minutes)
    ts = int(time.replace(minute=time.minute // minutes * minutes, second=0, microsecond=0).timestamp())
    return ts

def at_every_hours_min(minutes: int) -> int:
    time = datetime.now() + timedelta(hours=1)
    ts = int(time.replace(minute=minutes, second=0, microsecond=0).timestamp())
    return ts

CACHE_PATHS = {
    'GET': {},
    'POST': {},
    'GET-MATCH': {},
    'POST-MATCH': {},
    'PUT-MATCH': {},
}
CACHE_TYPE = {
    'no-exp':
        {
            'type': 'no-exp',
            'ttl': None,
        },
    'in-1m':
        {
            'type': 'duration',
            'ttl': 60,
        },
    'in-5m':
        {
            'type': 'duration',
            'ttl': 300,
        },
    'in-30m':
        {
            'type': 'duration',
            'ttl': 1800,
        },
    'in-1h':
        {
            'type': 'duration',
            'ttl': 3600,
        },
    'at-eh-m5':
        {
            'type': 'at-time',
            'ttl': at_every_hours_min(5),
        },
    'at-eh-m10':
        {
            'type': 'at-time',
            'ttl': at_every_hours_min(10),
        },
    'at-e5m':
        {
            'type': 'at-time',
            'ttl': at_every_n_min(5),
        },
    'at-e30m':
        {
            'type': 'at-time',
            'ttl': at_every_n_min(30),
        },
}

def get_cache_type(method: str, path: str) -> str | None:
    """ check if path is in cache list, return cache type if exist, else return None
    """
    path = path.strip().rstrip('/')
    try:
        return CACHE_PATHS[method][path]
    except Exception as e:
        for key in CACHE_PATHS[method+'-MATCH']:
            if re.match(key, path):
                return CACHE_PATHS[method+'-MATCH'][key]
        print(e)
        return None
    
# add path
def router_cache(router:APIRouter, prefix:str, cahce_type:str='in-1m', spec_method:str='ALL') -> None:
    spec_method = spec_method.upper()
    if spec_method == 'ALL':
        for route in router.routes:
            # skip path end with '/' to avoid duplicate cache
            if route.path[-1:] == '/':
                continue
            path = prefix+route.path
            if '{' in path and '}' in path:
                path = r'^' + re.sub(r'\{\w+\}', r'[^\/]+', path.replace(r'/',r'\/')) + r'$'
                for method in route.methods:
                    CACHE_PATHS[method+'-MATCH'][path] = cahce_type
            else:
                for method in route.methods:
                    CACHE_PATHS[method][path] = cahce_type
    else:
        for route in router.routes:
            # skip path end with '/' to avoid duplicate cache
            if route.path[-1:] == '/':
                continue
            path = prefix+route.path
            if spec_method in route.methods and '{' in path and '}' in path:
                path = r'^' + re.sub(r'\{\w+\}', '[^\/]+', path.replace('/','\/')) + r'$'
                for method in route.methods:
                    CACHE_PATHS[spec_method+'-MATCH'][path] = cahce_type
            else:
                if spec_method in route.methods:
                    CACHE_PATHS[spec_method][path] = cahce_type

# API-v1
# all path in search.router cache end at 10 min every hour
# router_cache(api_v1.search.router, "/api/v1/search", 'at-eh-m10', 'GET')
# prefix = "/api/v1/search"
# for route in api_v1.search.router.routes:
#     for method in route.methods:
#         if method == 'GET':
#             CACHE_PATHS[method][prefix+route.path] = 'at-eh-m10'
        # todo: add POST cache path -> add prossecing post body to hash key in middleware file

# all path in ai_analysis.router cache end at 5 min every hour
# router_cache(api_v1.ai_analysis.router, "/api/v1/ai-analysis", 'at-eh-m5')
# prefix = "/api/v1/ai-analysis"
# for route in api_v1.ai_analysis.router.routes:
#     for method in route.methods:
#         CACHE_PATHS[method][prefix+route.path] = 'at-eh-m5'

# all path in al_trade.router cache in 5 min
# router_cache(api_v1.al_trade.router, "/api/v1/al-trade", 'in-5m')
# prefix = "/api/v1/al-trade"
# for route in api_v1.al_trade.router.routes:
#     for method in route.methods:
#         CACHE_PATHS[method][prefix+route.path] = 'in-5m'
    # todo: cache and get cache in function, cache time depend on query params

# all path in search.router cache end at 5 min every hour
# router_cache(api_v1.prices.router, "/api/v1/prices", 'in-1m')
# prefix = "/api/v1/prices"
# for route in api_v1.prices.router.routes:
#     for method in route.methods:
#         CACHE_PATHS[method][prefix+route.path] = 'in-1m'

# todo: fix
# # API-v2
# router_cache(api_v2.prices.router, "/api/v2/prices", 'in-1m')
# router_cache(api_v2.ai_analysis.router, "/api/v2/ai-analysis", 'at-eh-m5')
# router_cache(api_v2.al_trade.router, "/api/v2/al-trade", 'in-5m')
# router_cache(api_v2.search.router, "/api/v2/search", 'at-eh-m10')

# # API-v2.1
# router_cache(api_v2_2.prices.router, "/api/v2_1/prices", 'in-1m')
# router_cache(api_v2_2.ai_analysis.router, "/api/v2_1/ai-analysis", 'at-eh-m5')
# router_cache(api_v2_2.al_trade.router, "/api/v2_1/al-trade", 'in-5m')
# # router_cache(api_v2_2.sub_info.router, "/api/v2_1/sub-info", 'in-1h')
# router_cache(api_v2_2.chat.router, "/api/v2_1/ai-chat", 'in-1h')


# print(CACHE_PATHS)
