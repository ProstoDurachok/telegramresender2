from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, PositiveInt, Field


class UserModel(BaseModel):
    id: PositiveInt
    user_id: PositiveInt
    role: Literal['admin', 'operator', 'user']  # Заменил 'false' на 'user'


class ChannelModel(BaseModel):
    id: Union[PositiveInt, None] = Field(default=None)
    user_id: PositiveInt
    channel_id: int
    channel_name: str
    channel_link: str


class GroupModel(BaseModel):
    id: PositiveInt
    user_id: PositiveInt
    group_name: str
    group_id: int


class PostModel(BaseModel):
    id: PositiveInt
    channel_id: int
    channel_name: str
    post_id: int
    post_text: str
    created_at: datetime
