from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        parent = super()
        if hasattr(parent, "model_validate"):
            return parent.model_validate(obj, *args, **kwargs)
        return cls.parse_obj(obj)

    def model_dump(self, *args, **kwargs):
        parent = super()
        if hasattr(parent, "model_dump"):
            return parent.model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs):
        parent = super()
        if hasattr(parent, "model_dump_json"):
            return parent.model_dump_json(*args, **kwargs)
        return self.json(*args, **kwargs)
