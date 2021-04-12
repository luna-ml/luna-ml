import unittest
import tempfile, os, io
import shutil
from datetime import datetime
from kubernetes import config
from task.executor import Executor
from task.task import Task

class TestExecutor(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._exc = Executor(self._tmpdir)
        config.load_kube_config()

    def tearDown(self):
        shutil.rmtree(self._tmpdir)

    def _createFile(self, path, content):
        dirname = os.path.dirname(path)
        os.makedirs(f"{self._tmpdir}/{dirname}", exist_ok = True)
        f = open(f"{self._tmpdir}/{path}", "w")
        f.write(content)
        f.close()

    def _readFile(self, path):
        dirname = os.path.dirname(path)
        os.makedirs(f"{self._tmpdir}/{dirname}", exist_ok = True)
        f = open(f"{self._tmpdir}/{path}", "r")
        c = f.read()
        f.close()

        return c

    def test_when_evaluate__then_run_task(self):
        # given task
        task = Task(
            taskId=int(datetime.now().timestamp()),
            image=["python:3.6", "python:3.6"],
            command=[["bash", "-c", "sleep 1"], ["bash", "-c", "sleep 1"]])

        # when evaluate
        ret = self._exc.evaluate(task)

        # then
        self.assertEqual(0, ret)

    def test_when_evaluate_with_file__then_file_transfers_between_container(self):
        # given project and model
        self._createFile("/proj1/file1", "a")
        self._createFile("/model1/file2", "b")

        task = Task(
            taskId=int(datetime.now().timestamp()),
            image=["python:3.6", "python:3.6"],
            command=[
                ["bash", "-c", "find /workspace/ > /workspace/eval/result"],
                ["bash", "-c", "echo -n 'score 1' > /workspace/score/scorefile"]
            ],
            copyToContainerBeforeStart=[
                ("/model1", "/workspace/model"),
                ("/proj1", "/workspace")
            ],
            copyFromContainerAfterFinish=[
                ("/workspace/eval", "/eval1"),
                ("/workspace/score", "/score1")
            ])

        # when evaluate
        ret = self._exc.evaluate(task)

        # then
        self.assertEqual(0, ret)
        result = self._readFile("/eval1/result")
        score = self._readFile("/score1/scorefile")

        self.assertEqual(True, "/workspace/file1" in result)
        self.assertEqual(True, "/workspace/model/file2" in result)
        self.assertEqual("score 1", score)


    def test_copy_tree_ignore(self):
        self._createFile("/proj1/file1", "a")
        self._createFile("/proj1/models/model1/file2", "b")

        shutil.copytree(
            f"{self._tmpdir}/proj1",
            f"{self._tmpdir}/proj2"
        )

        
