#!/usr/bin/env python

import os, sys, io, time
import fire
import requests
import logging
import json
from colorama import init
from luna_ml.repository.repo_reader import RepoReader
from luna_ml.api.project_yaml import ProjectYaml
from luna_ml.api.model_yaml import ModelYaml

init()
from colorama import Fore, Back, Style

class LunaCli(object):
    """Luna ML CLI."""

    def __init__(self, server="http://localhost:5000"):
        self._server = server.rstrip("/")

    def __json_from_response(self, resp):
        return json.loads(resp.text)

    def __get_bool_param(self, boolParam, defaultValue: bool):
        if boolParam == None or boolParam == "":
            return defaultValue

        if boolParam == True or boolParam == False:
            return boolParam

        v = boolParam.strip().lower()
        if "true" == v:
            return True

        if "false" == v:
            return False

        return None

    def sync(self, local_repo, orig_commit=None, current_commit=None, dry_run=False, eval=True, wait=False):
        """Sync local git repository to update leaderboard

        sync command take changes of local git repository and update
        the server. By default, it takes changes between the HEAD and
        the curent working tree. Optionally, you can make take changes
        between two different commits by specifying flags.

        e.g.
            # sync changes of the local github repo in current directory
            luna-ml sync .

            # sync changes of the local github repo in absolute path
            luna-ml sync /my/repo
        """

        dry_run = self.__get_bool_param(dry_run, False)
        eval = self.__get_bool_param(eval, True)
        wait = self.__get_bool_param(wait, False)

        repoPath = os.path.abspath(local_repo).rstrip("/")
        print(f"Scanning changes from local repo ({repoPath}) ...")

        r = RepoReader(
                repoPath,
                diffOrigHash=orig_commit,
                diffCurrHash=current_commit
            )

        projects = r.getAll()

        if 0 == len(projects):
            print("No changes detected")
            return

        print("")
        self._printProjectSummaryAsTable(projects, repoPath)
        print("")

        if dry_run:
            return

        if not "REPO_TYPE" in os.environ:
            logging.error("REPO_TYPE environment is not defined. REPO_TYPE is something like 'github.com'")
            sys.exit(1)

        if not "REPO_NAME" in os.environ:
            logging.error("REPO_NAME environment is not defined. REPO_NAME is something like 'owner/repo'")
            sys.exit(1)

        repoType = os.environ["REPO_TYPE"]
        repoName = os.environ["REPO_NAME"]
        lunaAccessToken = os.environ["LUNA_ACCESS_TOKEN"]

        # post changes
        for projectPath, project in projects.items():
            # projectPath is absolute path
            lunaYamlPath = f"{projectPath}/{ProjectYaml.FileName}"
            projectPathRelativeToRepoRoot = projectPath[len(repoPath):]
            modelBasePath = "{}/{}".format(
                projectPath,
                project["yaml"].modelBasePath.lstrip("/").rstrip("/")
            )

            # update project
            if project["action"] == "update":
                print("Update project '{}' ... ".format(project["yaml"].name), end='')
                files = [("file", (ProjectYaml.FileName, open(lunaYamlPath, "rb")))]

                for r in project["resources"]:
                    files.append(("file", (r[len(projectPath):], open(r, "rb"))))

                resp = requests.post(
                    f"{self._server}/v1/project",
                    data={
                        "access_token": lunaAccessToken,
                        "repo_type": repoType,
                        "repo_name": repoName,
                        "path": projectPathRelativeToRepoRoot,
                        "commit": project["commit"]
                    },
                    files=files
                )

                if not resp.status_code == 200:
                    print("failed {}. {}".format(resp.status_code, resp.text))
                    logging.error("Update project {} failed. {}".format(project["yaml"].name, resp.text))
                    sys.exit(1)

                respProject = self.__json_from_response(resp)
                projectId = respProject["id"]
                print("done. id: {}".format(projectId))
            else:
                # get project
                resp = requests.get(
                    f"{self._server}/v1/project",
                    params={
                        "repo_type": repoType,
                        "repo_name": repoName,
                        "path": projectPathRelativeToRepoRoot
                    }
                )

                if not resp.status_code == 200:
                    logging.warn("Project {} is not created.".format(project["yaml"].name))
                    continue

                respProject = self.__json_from_response(resp)
                projectId = respProject["id"]

            # update models
            for modelPath, model in project["models"].items():
                # modelPath is absolute path
                modelPathRelativeToModelBase = modelPath[len(modelBasePath):]
                if model["action"] == "update":
                    print("Update model '{}' ... ".format(model["yaml"].name), end='')

                    modelYamlPath = f"{modelPath}/{ModelYaml.FileName}"

                    files = []

                    if os.path.isfile(modelYamlPath):
                        files.append(("file", (ModelYaml.FileName, open(modelYamlPath, "rb"))))

                    for r in model["resources"]:
                        files.append(("file", (r[len(modelPath.rstrip("/")):], open(r, "rb"))))

                    resp = requests.post(
                        f"{self._server}/v1/project/{projectId}/model",
                        data={
                            "access_token": lunaAccessToken,
                            "repo_type": repoType,
                            "repo_name": repoName,
                            "path": modelPathRelativeToModelBase,
                            "commit": project["commit"]
                        },
                        files=files
                    )

                    if not resp.status_code == 200:
                        print("failed {}. {}".format(resp.status_code, resp.text))
                        logging.error("Update model {} failed. {}".format(project["yaml"].name, resp.text))
                        sys.exit(1)
                    respModel = self.__json_from_response(resp)
                    modelId = respModel["id"]
                    print("done. id: {}".format(modelId))

                    if not eval:
                        continue

                    # trigger evaluation
                    print("trigger evaluation ... ")
                    for ev in project["yaml"].evaluators:
                        resp = requests.post(
                            f"{self._server}/v1/project/{projectId}/model/{modelId}/eval",
                            data={
                                "access_token": lunaAccessToken,
                                "name": ev.name
                            }
                        )

                        if not resp.status_code == 200:
                            print("Trigger evaluation failed. {} ".format(resp.status_code))
                            sys.exit(1)

                        if not wait:
                            continue

                        taskList = self.__json_from_response(resp)
                        if len(taskList) == 0:
                            continue

                        task = taskList[0] # because we're evaluating one by one here
                        taskId = task["id"]

                        print(f"Wait for the evaluation to finish ... ")
                        while "exit_code" not in task or task["exit_code"] == None:
                            time.sleep(5)

                            resp = requests.get(
                                f"{self._server}/v1/project/{projectId}/model/{modelId}/eval/{taskId}"
                            )

                            if not resp.status_code == 200:
                                print(f"Failed to get evaluation task {taskId}. {resp.status_code}")
                                sys.exit(1)

                            task = self.__json_from_response(resp)

                        if "exit_code" in task:
                            if task["exit_code"] != 0:
                                print(f"Task exited with {task['exit_code']} exit code.")
                                sys.exit(1)
                            else:
                                continue
                        else:
                            # should not reach here.
                            sys.exit(1)

    def _printProjectSummaryAsTable(self, projects, repoPath):
        projectList = list(projects.items())
        projectList.sort(key=lambda item: item[1]["yaml"].name)

        title_len = 30
        Col_Margin = "   "

        # print header
        print("{}{:<30}{}{:<10}{}{:<30}{}".format(
            Style.DIM,
            "Project",
            Col_Margin,
            "Change",
            Col_Margin,
            "Path",
            Style.RESET_ALL
        ))

        # print rows
        for path, project in projectList:
            title=project["yaml"].name
            title=title if len(title) <= title_len else f"{title[:title_len-2]}.."
            print("{:<30}{}{:<10}{}{:<30}".format(
                title,
                Col_Margin,
                project["action"] if project["action"] else "none",
                Col_Margin,
                path[len(repoPath):]
            ))

            # print models
            modelList = list(project["models"].items())
            modelList.sort(key=lambda item: item[1]["yaml"].name)

            model_count = 1
            for path, model in modelList:
                title=model["yaml"].name
                title=title if len(title) <= title_len else f"{title[:title_len-2]}.."

                if model_count == 1:
                    Model_Indent = "{}{:>15}{}".format(
                        Style.DIM,
                        "Models    ",
                        Style.RESET_ALL,
                    )
                else:
                    Model_Indent = "{:<15}".format("")

                print("{}{:<15}{}{:<10}{}{:<30}".format(
                    Model_Indent,
                    title,
                    Col_Margin,
                    model["action"] if model["action"] else "none",
                    Col_Margin,
                    path[len(repoPath):]
                ))

                model_count = model_count + 1
