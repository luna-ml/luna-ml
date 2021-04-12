import yaml

class ProjectYaml():
    FileName = "luna.yaml"

    def __init__(
            self,
            yamlText: str
    ):

        o = yaml.load(
            yamlText,
            Loader=yaml.SafeLoader
        )


        ProjectYaml._shouldNotEmpty(o, [
            "version",
            "kind",
            "name",
            "evaluators",
            "scorer"
        ])

        self.version = o.get("version")
        self.kind = o.get("kind")
        self.name = o.get("name")
        self.description = o.get("description")
        self.media = o.get("media")
        self.modelBasePath = o.get("modelBasePath", "/models")

        self.evaluators = [self.Evaluator(e) for e in o.get("evaluators")]
        self.scorer = self.Scorer(o.get("scorer"))

        # check duplicate evaluator name
        evNames = [e.name for e in self.evaluators]
        evUniqueNames = set(evNames)
        if len(evNames) != len(evUniqueNames):
            raise ValueError("Duplicate evaluator name")

    def toYaml(self) -> str:
        return yaml.dump(self)

    @classmethod
    def _shouldNotEmpty(self, o, labels, path = ""):
        for l in labels:
            if o.get(l) == None or o.get(l) == "":
                raise ValueError("'{}{}' is missing in {}".format(path, l, ProjectYaml.FileName))

    class Evaluator:
        def __init__(
            self,
            o
        ):
            ProjectYaml._shouldNotEmpty(o, [
                "name",
                "image"
            ], "evaluators[].")

            self.name = o.get("name")
            self.image = o.get("image")
            self.command = o.get("command")
            self.models = o.get("models")

    class Scorer:
        def __init__(
            self,
            o
        ):
            ProjectYaml._shouldNotEmpty(o, [
                "image"
            ], "scorer.")

            self.image = o.get("image")
            self.command = o.get("command")
            self.modelPath = o.get("evalOutputFilter", "*")
            self.scoreFieldName = o.get("scoreFieldName", "score")
            self.sort = o.get("sort", "desc")
