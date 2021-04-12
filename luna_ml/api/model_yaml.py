import yaml

class ModelYaml():
    FileName = "model.yaml"

    def __init__(
            self,
            yamlText: str
    ):

        o = yaml.load(
            yamlText,
            Loader=yaml.SafeLoader
        )

        ModelYaml._shouldNotEmpty(o, [
            "version",
            "kind",
            "name"
        ])

        self.version = o.get("version")
        self.kind = o.get("kind")
        self.name = o.get("name")

    def toYaml(self) -> str:
        return yaml.dump(self)

    @classmethod
    def default(cls, name: str):
        yaml = f"""
        version: v1
        kind: luna-ml/model
        name: {name}
        """
        return ModelYaml(yaml)

    @classmethod
    def _shouldNotEmpty(self, o, labels, path = ""):
        for l in labels:
            if o.get(l) == None or o.get(l) == "":
                raise ValueError("'{}{}' is missing in {}".format(path, l, ModelYaml.FileName))
