import yaml

# make pyyaml don't include tag when dump. such as "!!python/object:api.project_yaml"
# see https://stackoverflow.com/a/48823424/2952665
def noop(self, *args, **kw):
    pass
yaml.emitter.Emitter.process_tag = noop
