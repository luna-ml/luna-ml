from git import Repo, InvalidGitRepositoryError
import glob
import sys, os
import logging
from datetime import datetime
import time
from git import Commit
from luna_ml.api.project_yaml import ProjectYaml
from luna_ml.api.model_yaml import ModelYaml

class RepoReader():
    def __init__(self, repoRootDir, diffOrigHash=None, diffCurrHash=None):
        self._repoRootDir = repoRootDir
        self._projects = {}

        self._repo = Repo(repoRootDir)

        if diffCurrHash == None: # working tree
            ts = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            self._commit = f"working_tree {ts}"
        else:
            if isinstance(diffCurrHash, Commit):
                self._commit = diffCurrHash.hexsha
            else:
                self._commit = self._repo.rev_parse(diffCurrHash).hexsha

        # diff and scan
        diff = self._gitDiff(orig=diffOrigHash, current=diffCurrHash)
        self.scan(diff=diff)

    def getAll(self):
        return self._projects

    def scan(self, diff=None):
        lunaYamlPathList = []
        modelBasePathList = []

        # scan subdirs to find luna.yaml, and load
        for filename in glob.iglob("{}/**/{}".format(self._repoRootDir.rstrip("/"), ProjectYaml.FileName), recursive=True):
            lunaYamlPathList.append(filename)

        for filename in lunaYamlPathList:
            with open(filename, 'r') as file:
                yaml = file.read()
                projectYaml = ProjectYaml(yaml)

            projectBase = os.path.dirname(filename).rstrip("/")

            modelBasePath = "{}/{}".format(
                projectBase,
                projectYaml.modelBasePath.lstrip("/")
            )
            modelBasePathList.append(modelBasePath)

            # project resources
            resources = []
            allFilesUnderProject = glob.glob("{}/**".format(projectBase), recursive=True)
            allFilesUnderModelBase = glob.glob("{}/**".format(modelBasePath), recursive=True)
            notPartOfResource = [filename, modelBasePath]
            localEvalResult = glob.glob("{}/eval/**".format(projectBase), recursive=True)
            localScoreResult = glob.glob("{}/eval/**".format(projectBase), recursive=True)
            pycache = glob.glob("{}/__pycache__/**".format(projectBase), recursive=True)

            # filter files only
            allFilesUnderProject = [f for f in allFilesUnderProject if os.path.isfile(f)]

            # build project resources
            resources = list(set(allFilesUnderProject) - set(allFilesUnderModelBase) - set(notPartOfResource) - set(localEvalResult) - set(localScoreResult) - set(pycache))

            # retreive action
            if diff == None:
                action = "update" # when no diff is provided, consider it modified
                renamedFrom = None
            else:
                action, renamedFrom = self._getActionForProject(diff, os.path.dirname(filename), modelBasePath)

            # get model dict
            models = {}
            for modelDir in glob.glob("{}/*".format(modelBasePath)):
                if not os.path.isdir(modelDir):
                    continue

                m = self._scan_model(modelDir, diff=diff)
                models[modelDir] = m

            self._projects[projectBase] = {
                "yaml": projectYaml,
                "models": models,
                "modelBasePath": modelBasePath, # absolute path
                "resources": resources, # list of resource files. absolute path
                "action": action, # action need to be taken for this project. "update", "delete", "rename". None for no change
                "renamedFrom": renamedFrom, # previous luna.yaml file path, in case of action is "rename"
                "commit": self._commit
            }

    def _scan_model(self, path, diff=None):
        path = path.rstrip("/")
        modelYamlPath = "{}/{}".format(path, ModelYaml.FileName)

        # resources
        allFilesUnderModel = glob.glob("{}/**".format(path), recursive=True)
        notPartOfResource = [modelYamlPath]
        pycache = glob.glob("{}/__pycache__/**".format(path), recursive=True)

        # filter files only
        allFilesUnderModel = [f for f in allFilesUnderModel if os.path.isfile(f)]

        resources = list(set(allFilesUnderModel) - set(notPartOfResource) - set(pycache))

        # if ModelYaml.FileName does not exists, create a default one
        if os.path.isfile(modelYamlPath):
            with open(modelYamlPath, 'r') as file:
                yaml = file.read()
                modelYaml = ModelYaml(yaml)
        else:
            modelYaml = ModelYaml.default(os.path.basename(os.path.dirname(modelYamlPath)))

        action, renamedFrom = self._getActionForModel(diff, path)

        return {
            "yaml": modelYaml,
            "resources": resources,
            "action": action,
            "commit": self._commit
        }

    def _gitDiff(self, orig, current=None):
        '''
        current:
          None for working tree
          'HEAD' for head
        '''

        diff = {
            "added": [],
            "modified": [],
            "renamed": [],
            "deleted": []
        }

        untracked = []
        for f in self._repo.untracked_files:
            untracked.append("{}/{}".format(self._repoRootDir, f))

        if orig == None and current == None:
            diff["added"] = untracked
            return diff

        if orig == None:
            origIndex = self._repo.index
        elif isinstance(orig, Commit):
            origIndex = orig
        else:
            origIndex = self._repo.rev_parse(orig)

        if current == None:
            currentIndex = None
        elif isinstance(current, Commit):
            currentIndex = current
        else:
            currentIndex = self._repo.rev_parse(current)

        diffIndex = origIndex.diff(currentIndex)
        for diffItem in diffIndex.iter_change_type("A"):
            diff["added"].append("{}/{}".format(self._repoRootDir, diffItem.b_path))

        for diffItem in diffIndex.iter_change_type("M"):
            diff["modified"].append("{}/{}".format(self._repoRootDir, diffItem.b_path))

        for diffItem in diffIndex.iter_change_type("R"):
            diff["renamed"].append(
                ("{}/{}".format(self._repoRootDir, diffItem.a_path),
                "{}/{}".format(self._repoRootDir, diffItem.b_path))
            )

        for diffItem in diffIndex.iter_change_type("D"):
            diff["deleted"].append("{}/{}".format(self._repoRootDir, diffItem.b_path))

        if current == None:
            diff["added"].extend(untracked)

        return diff

    def _getActionForProject(self, diff, projectPath, modelbasePath):
        filteredDiff = {
            "added": self._filterChangedFileListForProject(diff["added"], projectPath, modelbasePath),
            "modified": self._filterChangedFileListForProject(diff["modified"], projectPath, modelbasePath),
            "deleted": self._filterChangedFileListForProject(diff["deleted"], projectPath, modelbasePath),
            "renamed": self._filterChangedFileListForProject(diff["renamed"], projectPath, modelbasePath)
        }

        yamlPath = "{}/{}".format(projectPath, ProjectYaml.FileName)

        # action is delete when luna.yaml is deleted
        if yamlPath in filteredDiff["deleted"]:
            return ("delete", None)
        
        # action is rename when luna.yaml is renamed
        for ren in filteredDiff["renamed"]:
            if ren[1] == yamlPath:
                return ("rename", ren[0])

        # action is update for any other changes
        if len(filteredDiff["added"]) + len(filteredDiff["modified"]) + len(filteredDiff["deleted"]) + len(filteredDiff["renamed"]) > 0:
            return ("update", None)

        # no action required
        return (None, None)

    def _getActionForModel(self, diff, modelPath):
        filteredDiff = {
            "added": self._filterChangedFileListForModel(diff["added"], modelPath),
            "modified": self._filterChangedFileListForModel(diff["modified"], modelPath),
            "deleted": self._filterChangedFileListForModel(diff["deleted"], modelPath),
            "renamed": self._filterChangedFileListForModel(diff["renamed"], modelPath)
        }

        yamlPath = "{}/{}".format(modelPath, ModelYaml.FileName)

        # for now, model delete, rename is not supported.

        # action is update for any changes
        if len(filteredDiff["added"]) + len(filteredDiff["modified"]) + len(filteredDiff["deleted"]) + len(filteredDiff["renamed"]) > 0:
            return ("update", None)

        # no action required
        return (None, None)


    def _filterChangedFileListForProject(self, changedFileList, projectPath, modelbasePath):
        changedFileInTheProject = [f for f in changedFileList if (isinstance(f, tuple) and f[1].startswith(projectPath)) or (isinstance(f, str) and f.startswith(projectPath))]
        changedFileInTheProjectExcludeModels = [f for f in changedFileInTheProject if not ((isinstance(f, tuple) and f[1].startswith(modelbasePath)) or (isinstance(f, str) and f.startswith(modelbasePath)))]
        return changedFileInTheProjectExcludeModels

    def _filterChangedFileListForModel(self, changedFileList, modelPath):
        changedFileListForModel = [f for f in changedFileList if (isinstance(f, tuple) and f[1].startswith(modelPath)) or (isinstance(f, str) and f.startswith(modelPath))]
        return changedFileListForModel
