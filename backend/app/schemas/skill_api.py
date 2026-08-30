from pydantic import BaseModel


class SkillTaxonomyEntry(BaseModel):
    canonical_name: str
    category: str
    source: str
    aliases: list[str]


class SkillTaxonomyResponse(BaseModel):
    skills: list[SkillTaxonomyEntry]
    total: int
