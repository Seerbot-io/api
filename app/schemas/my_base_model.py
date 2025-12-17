from typing import Any

from pydantic import BaseModel


class CustormBaseModel(BaseModel):
    """Custom base model for all schemas.
    - pre-process the data before init
    - set the default value if the value is invalid
    - check the serialization fields (todo)
    - helper function to check the validation fields
    """

    def __init__(self, **data: Any) -> None:
        default_value = 0
        for attr, value in data.items():
            attr_type = None
            me = self.__class__
            # parent = self.__base__
            while attr_type is None and me != CustormBaseModel:
                try:
                    attr_type = me.__annotations__[attr]
                except Exception:
                    if me.__base__ is not None:
                        me = me.__base__
                    else:
                        break
                    # parent = self.__base__
                    continue

            # process simple type
            if attr_type in (int, float, str, bool, dict):
                try:  #  try to convert the value to the type of the attribute
                    data[attr] = attr_type(value)
                except Exception:
                    print(f"Invalid value for key: {attr}")
                    if hasattr(
                        self, attr
                    ):  # set the default value if the value is invalid
                        print(f"Set default value for key: {attr}", getattr(self, attr))
                        data[attr] = getattr(self, attr)
                    else:  # set the custorm default value it don't have default value
                        print(
                            f"Set custorm default value for key: {attr}",
                            getattr(self, attr),
                        )
                        # Use appropriate default value based on type
                        if attr_type is dict:
                            data[attr] = {}
                        elif attr_type is str:
                            data[attr] = ""
                        elif attr_type is bool:
                            data[attr] = False
                        elif attr_type is int:
                            data[attr] = int(default_value)
                        elif attr_type is float:
                            data[attr] = float(default_value)
                        else:
                            # For complex types, skip or set to None
                            # Don't try to construct with default_value
                            pass
            else:
                pass
                # todo
        super().__init__(**data)

    # for serialization fileds
    def check_serialization(self):
        pass


class Message(CustormBaseModel):
    message: str = ""
    status_code: int = 200
