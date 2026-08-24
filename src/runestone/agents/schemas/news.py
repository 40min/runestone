"""News citation and specialist article payloads for agent responses."""

from pydantic import BaseModel, Field, HttpUrl


class NewsSource(BaseModel):
    """News source metadata for assistant responses."""

    title: str = Field(..., description="Headline/title of the news article")
    url: HttpUrl = Field(..., description="URL of the news article")
    date: str = Field(..., description="Published date string as returned by search")


class NewsSpecialistArticle(BaseModel):
    """Structured news article payload produced by NewsAgent."""

    title: str = Field(..., description="Headline/title of the news article")
    url: HttpUrl = Field(..., description="URL of the news article")
    date: str = Field(..., description="Published date string as returned by search")
    snippet: str = Field("", description="Short summary or snippet used for teacher composition")
    article_text: str = Field("", description="Optional extracted article text when NewsAgent read the article")
