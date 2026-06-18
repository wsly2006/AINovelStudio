from pydantic import BaseModel, ConfigDict, Field


class PromptItem(BaseModel):
    """列表里的一项,带元数据 + 当前生效的内容。"""

    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    group: str
    description: str
    placeholders: list[str]
    system_text: str
    user_template: str
    customized: bool
    default_system: str
    default_user: str


class PromptUpdate(BaseModel):
    system_text: str = Field(default="", max_length=20000)
    user_template: str = Field(min_length=1, max_length=20000)
