import unittest
from repository.repo_reader import RepoReader
import tempfile, os
import shutil
from git import Repo

class TestStorage(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._repo = Repo.init(self._tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self._tmpdir)

    def _create_luna_yaml(self, path, name, yaml=None):
        yaml = yaml if yaml is not None else f"""
        name: {name}
        version: v1
        kind: luna-ml/project
        evaluators:
        - name: ev1
          image: python:3.7
        scorer:
          image: python:3.7
        """

        absolutePath = "{}{}".format(self._tmpdir, path)
        os.makedirs(os.path.dirname(absolutePath), exist_ok=True)
        with open(absolutePath, "w") as luna_yaml:
            print(yaml, file=luna_yaml)

    def _create_file(self, path, content):
        absolutePath = "{}{}".format(self._tmpdir, path)
        os.makedirs(os.path.dirname(absolutePath), exist_ok=True)
        with open(absolutePath, "w") as fileo:
            print(content, file=fileo)

    def test_when_project_exists_on_root__then_should_able_to_list(self):
        # given
        self._create_luna_yaml("/luna.yaml", "proj1")

        # when
        r = RepoReader(self._tmpdir)

        # then
        self.assertEqual(1, len(r._projects))
        self.assertEqual("proj1", r._projects["{}".format(self._tmpdir)]["yaml"].name)

    def test_when_projects_exist_on_dirs__then_should_able_to_list(self):
        # given
        self._create_luna_yaml("/proj1/luna.yaml", "proj1")
        self._create_luna_yaml("/proj2/luna.yaml", "proj2")

        # when
        r = RepoReader(self._tmpdir)

        # then
        self.assertEqual(2, len(r._projects))

    def test_when_invalid_luna_yaml__then_should_raise_exception(self):
        # given
        self._create_luna_yaml("/proj1/luna.yaml", "proj1") # valid
        self._create_luna_yaml("/proj2/luna.yaml", "proj2", yaml=
            """
            name: proj2
            version: v1
            kind: luna-ml/project
            scorer:
                image: python:3.7
            """
        ) # invalid. missing evaluator

        # when
        self.assertRaises(Exception, RepoReader, self._tmpdir)

    def test_when_projects_exist_on_dirs__then_should_able_to_list_resources(self):
        # given 2 projects
        self._create_luna_yaml("/proj1/luna.yaml", "proj1")
        self._create_luna_yaml("/proj2/luna.yaml", "proj2")

        # given file not belongs to any project
        self._create_file("/file1", "v1")

        # given files belongs to project
        self._create_file("/proj1/file12", "v12")
        self._create_file("/proj1/subdir/file13", "v13")

        # given file under the model path
        self._create_file("/proj1/models/file14", "v14")

        # given file belongs to another project
        self._create_file("/proj2/file25", "v25")

        # when
        r = RepoReader(self._tmpdir)

        # then
        self.assertEqual(2, len(r._projects))

        # then
        proj1 = r._projects["{}/proj1".format(self._tmpdir)]
        self.assertEqual(2, len(proj1["resources"]))
        self.assertTrue("{}/proj1/file12".format(self._tmpdir) in proj1["resources"])
        self.assertTrue("{}/proj1/subdir/file13".format(self._tmpdir) in proj1["resources"])

        proj2 = r._projects["{}/proj2".format(self._tmpdir)]
        self.assertEqual(1, len(proj2["resources"]))
        self.assertTrue("{}/proj2/file25".format(self._tmpdir) in proj2["resources"])


    def test_when_models_exist__then_should_able_to_list(self):
        # given 2 projects
        self._create_luna_yaml("/proj1/luna.yaml", "proj1")
        self._create_luna_yaml("/proj2/luna.yaml", "proj2")

        # given file under the model path
        self._create_file("/proj1/models/file11", "v1") # should be ignored, since it is not inside of individual model dir

        # given file under the model path
        self._create_file("/proj1/models/m1/file12", "v112")
        self._create_file("/proj1/models/m1/sudir/file13", "v113")
        self._create_file("/proj1/models/m2/file23", "v123")

        # given file under the model in another project
        self._create_file("/proj2/models/m3/file24", "v234")
        self._create_file("/proj2/models/m3/model.yaml", """
        version: v1
        kind: luna-ml/model
        name: "my model 3"
        """)

        # when
        r = RepoReader(self._tmpdir)

        # then two projects
        self.assertEqual(2, len(r._projects))

        # then num models
        proj1 = r._projects["{}/proj1".format(self._tmpdir)]
        proj2 = r._projects["{}/proj2".format(self._tmpdir)]
        self.assertEqual(2, len(proj1["models"]))
        self.assertEqual(1, len(proj2["models"]))

        # then model name is dir name when model.yaml is missing
        model1 = proj1["models"]["{}/proj1/models/m1".format(self._tmpdir)]
        model2 = proj1["models"]["{}/proj1/models/m2".format(self._tmpdir)]
        model3 = proj2["models"]["{}/proj2/models/m3".format(self._tmpdir)]
        self.assertEqual("m1", model1["yaml"].name)
        self.assertEqual("m2", model2["yaml"].name)

        # then model name from yaml when model.yaml exists
        self.assertEqual("my model 3", model3["yaml"].name)

        # then model resources
        self.assertTrue(2, len(model1["resources"]))
        self.assertTrue(1, len(model2["resources"]))
        self.assertTrue(1, len(model3["resources"]))

    def test_filterChangedFileListForProject(self):
        r = RepoReader(self._tmpdir)

        self.assertEqual(
            ["/proj1/luna.yaml", "/proj1/res1"],
            r._filterChangedFileListForProject(
                changedFileList=["/proj1/luna.yaml", "/proj1/res1", "/proj1/models/file1", "/proj2/luna.yaml"],
                projectPath="/proj1",
                modelbasePath="/proj1/models"
        ))

        self.assertEqual(
            ["/proj2/luna.yaml"],
            r._filterChangedFileListForProject(
                changedFileList=["/proj1/luna.yaml", "/proj1/res1", "/proj1/models/file1", "/proj2/luna.yaml"],
                projectPath="/proj2",
                modelbasePath="/proj2/models"
        ))

        self.assertEqual(
            [],
            r._filterChangedFileListForProject(
                changedFileList=["/proj1/luna.yaml", "/proj1/res1", "/proj1/models/file1", "/proj2/luna.yaml"],
                projectPath="/proj3",
                modelbasePath="/proj3/models"
        ))


    def test_filterChangedFileListForModel(self):
        r = RepoReader(self._tmpdir)

        self.assertEqual(
            ["/proj1/models/m1/file1"],
            r._filterChangedFileListForModel(
                changedFileList=["/proj1/luna.yaml", "/proj1/res1", "/proj1/models/file1", "/proj1/models/m1/file1", "/proj1/models/m2/file2"],
                modelPath="/proj1/models/m1"
        ))

    def test_when_diff_on_working_tree__then_should_return_both_untracked_added(self):
        # given
        self._create_file("/untracked", "v1")
        self._create_file("/added", "v12")
        self._create_file("/commited", "v13")

        # when
        r = RepoReader(self._tmpdir)
        r._repo.git.add(f"{self._tmpdir}/commited")
        r._repo.index.commit("initial commit")
        r._repo.git.add(f"{self._tmpdir}/added")

        diff = r._gitDiff(orig="HEAD", current=None)

        # then
        self.assertEqual(2, len(diff["added"]))
        self.assertTrue(f"{self._tmpdir}/added" in diff["added"])
        self.assertTrue(f"{self._tmpdir}/untracked" in diff["added"])

    def test_when_diff_against_repo_without_commit__then_should_return_all_untracked_as_added(self):
        # given
        self._create_file("/untracked1", "v1")
        self._create_file("/untracked2", "v12")

        # when
        r = RepoReader(self._tmpdir)
        diff = r._gitDiff(orig=None, current=None)

        # then
        self.assertEqual(2, len(diff["added"]))
        self.assertTrue(f"{self._tmpdir}/untracked1" in diff["added"])
        self.assertTrue(f"{self._tmpdir}/untracked2" in diff["added"])

    def test_when_diff_between_two_commit__then_should_return_all_changes(self):
        # given
        self._create_file("/unchanged", "v1")
        self._create_file("/modified", "v11")
        self._create_file("/added", "v12")
        self._create_file("/deleted", "v13")
        self._create_file("/renamed-a", "v14")
        self._create_file("/untracked", "v15")

        # when
        r = RepoReader(self._tmpdir)
        r._repo.git.add(f"{self._tmpdir}/unchanged")
        r._repo.git.add(f"{self._tmpdir}/modified")
        r._repo.git.add(f"{self._tmpdir}/deleted")
        r._repo.git.add(f"{self._tmpdir}/renamed-a")
        initialCommit = r._repo.index.commit("initial commit")

        self._create_file("/modified", "v11-1")
        r._repo.git.add(f"{self._tmpdir}/modified")
        r._repo.git.add(f"{self._tmpdir}/added")
        r._repo.index.remove([f"{self._tmpdir}/deleted"])
        r._repo.index.remove([f"{self._tmpdir}/renamed-a"])
        self._create_file("/renamed-b", "v14")
        r._repo.git.add(f"{self._tmpdir}/renamed-b")
        currentCommit = r._repo.index.commit("second commit")

        # then
        diff = r._gitDiff(orig=initialCommit.hexsha, current=currentCommit.hexsha)
        self.assertEqual([f"{self._tmpdir}/added"], diff["added"])
        self.assertEqual([f"{self._tmpdir}/modified"], diff["modified"])
        self.assertEqual([f"{self._tmpdir}/deleted"], diff["deleted"])
        self.assertEqual([(f"{self._tmpdir}/renamed-a", f"{self._tmpdir}/renamed-b")], diff["renamed"])

    def test_when_project_create_in_empty_repo__then_action_should_be_update(self):
        # given
        self._create_luna_yaml("/luna.yaml", "proj1")

        # when
        r = RepoReader(self._tmpdir)

        # then
        proj = r._projects["{}".format(self._tmpdir)]
        self.assertEqual("update", proj["action"])

    def test_when_project_has_no_change__then_action_should_be_none(self):
        # given
        self._create_luna_yaml("/luna.yaml", "proj1")
        self._repo.git.add(f"{self._tmpdir}")
        initialCommit = self._repo.index.commit("initial commit")

        # when
        r = RepoReader(self._tmpdir)

        # then
        proj = r._projects["{}".format(self._tmpdir)]
        self.assertEqual(None, proj["action"])

    def test_when_project_is_modified__then_action_should_be_update(self):
        # given
        self._create_luna_yaml("/luna.yaml", "proj1")
        self._create_file("/res1", "resource1")
        self._repo.git.add(f"{self._tmpdir}/luna.yaml")
        self._repo.git.add(f"{self._tmpdir}/res1")
        initialCommit = self._repo.index.commit("initial commit")
        self._repo.index.remove(f"{self._tmpdir}/res1")
        secondCommit = self._repo.index.commit("remove resource")
        os.remove(f"{self._tmpdir}/res1")

        # when
        r = RepoReader(self._tmpdir, initialCommit, secondCommit)

        # then
        proj = r._projects["{}".format(self._tmpdir)]
        self.assertEqual("update", proj["action"])

    def test_when_model_add__then_action_should_be_update(self):
        # given
        self._create_luna_yaml("/luna.yaml", "proj1")
        self._create_file("/models/m1/file", "")

        # when
        r = RepoReader(self._tmpdir)

        # then
        proj = r._projects["{}".format(self._tmpdir)]
        model = proj["models"]["{}/models/m1".format(self._tmpdir)]
        self.assertEqual("update", model["action"])
