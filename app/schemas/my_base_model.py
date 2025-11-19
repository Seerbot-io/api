import re
from pydantic import BaseModel

class CustormBaseModel(BaseModel):
    # pre-process the data before init
    def __init__(self, **data: any) -> None:
        default_value = 0
        for attr, value in data.items():
            attr_type = None
            me = self.__class__
            # parent = self.__base__
            while attr_type is None and me != CustormBaseModel:
                try:
                    attr_type = me.__annotations__[attr]
                except Exception as e:
                    me = me.__base__
                    # parent = self.__base__
                    continue
                
            # process simple type
            if attr_type in (int, float, str, bool, dict):
                try:  #  try to convert the value to the type of the attribute
                    data[attr] = attr_type(value)
                except Exception as e:
                    print(f"Invalid value for key: {attr}") 
                    if hasattr(self, attr):  # set the default value if the value is invalid
                        print(f"Set default value for key: {attr}", getattr(self, attr))
                        data[attr] = getattr(self, attr)
                    else: # set the custorm default value it don't have default value
                        print(f"Set custorm default value for key: {attr}", getattr(self, attr))
                        data[attr] = attr_type(default_value)
            else:
                pass
                # todo
        super().__init__(**data)

    # for serialization fileds 
    def check_serialization(self):
        pass


class Message(CustormBaseModel):
    message: str = ''
    status_code: int = 200
