import os, yaml, logging, threading, io, sys
from kubernetes import client, config, watch
from kubernetes.stream import stream
import tarfile
from tarfile import TarInfo
from tempfile import TemporaryFile
import base64
import time
from base64io import Base64IO
import pkgutil
from jinja2 import Template

from .kube_apply import createOrUpdateOrReplace, deleteObject
from .task import Task
from luna_ml.storage.storage_localfs import LocalFsStorage
from luna_ml.api.score_file import ScoreFile

logger = logging.getLogger(__name__)

class Executor():
    SharedVolumeMount = "/workspace"
    ModelContainerPath = "/workspace/model"
    EvalResultContainerPath = "/workspace/eval"
    ScoreResultContainerPath = "/workspace/score"

    """
    Run tasks on Kubernetes cluster.
    Assume each task is executed by 'Job' resource in kuberentes.
    And all Jobs are running in the same namespace.
    """
    def __init__(
        self,
        basePath, # basePath of the local clone of the repository
        kube_client=None,
        namespace="default"):
        self._kube_client = kube_client
        self._namespace = namespace
        self._storage = LocalFsStorage(basePath)

    def evaluate(self, task):
        podName = f"luna-{task.id}"
        self._startTask(task)
        self._waitForContainerReady(self._namespace, podName, "pre-task")
        self._copyDataToContainer(self._namespace, podName, "pre-task", task)
        ret = self._waitForContainerExit(self._namespace, podName, "task-1")
        if ret != 0:
            logger.info(f"Evaluator terminated with exit code {ret}")
            return ret
        self._waitForContainerExit(self._namespace, podName, "task-2")
        if ret != 0:
            logger.info(f"Scorer terminated with exit code {ret}")
            return ret
        self._waitForContainerReady(self._namespace, podName, "post-task")
        self._copyDataFromContainer(self._namespace, podName, "post-task", task)
        self._removePod(self._namespace, podName)

        return 0

    def _startTask(self, task):
        template = self._getTemplate("task-k8s-pod.yaml")
        jobTemplate = self._renderTemplate(template, task)
        yamls = yaml.safe_load_all(jobTemplate)

        # If it is a list type, will need to iterate its items
        failures = []
        k8s_objects = {}
        applied_yamls = {}

        for yamlDoc in yamls:
            try:
                created = createOrUpdateOrReplace(
                    yamlDoc,
                    client=self._kube_client
                )
                key = f"{created.metadata.namespace}/{created.kind}/{created.metadata.name}"
                k8s_objects[key] =created
                applied_yamls[key] = yamlDoc
            except Exception as api_exception:
                logging.error("Error", api_exception, exc_info=True)
                failures.append(api_exception)

        if failures:
            for _, yamlDoc in applied_yamls.items():
                deleteObject(yamlDoc, self._kube_client, namespace=self._namespace)
            raise Exception(failures)

    def _removePod(self, namespace, podName):
        corev1 = client.CoreV1Api(self._kube_client)

        # todo: remove all types of object by label selector
        body = client.V1DeleteOptions(propagation_policy='Background')
        corev1.delete_namespaced_pod(podName, namespace, body=body)


    def _waitForContainerExit(self, namespace, podName, containerName):
        corev1 = client.CoreV1Api(self._kube_client)

        while True:
            pod = corev1.read_namespaced_pod(podName, namespace)
            if pod == None or pod.status == None or pod.status.init_container_statuses == None:
                logging.info(f"Waiting for pod {podName} start")
                time.sleep(1)
                continue

            containerStatusList = pod.status.init_container_statuses
            filteredContainerStatuses = list(filter(lambda s: s.name == containerName, containerStatusList))

            if len(filteredContainerStatuses) == 0:
                logging.info(f"Container status not ready {podName}:{containerName}")
                time.sleep(1)
                continue

            status = filteredContainerStatuses[0]
            if status.state.terminated:
                return status.state.terminated.exit_code
            else:
                time.sleep(2)
                continue

    def _waitForContainerReady(self, namespace, podName, containerName):
        corev1 = client.CoreV1Api(self._kube_client)

        while True:
            pod = corev1.read_namespaced_pod(podName, namespace)
            if pod == None or pod.status == None or pod.status.init_container_statuses == None:
                logging.info(f"Waiting for pod {podName} start")
                time.sleep(1)
                continue

            containerStatusList = pod.status.init_container_statuses
            filteredContainerStatuses = list(filter(lambda s: s.name == containerName, containerStatusList))

            if len(filteredContainerStatuses) == 0:
                logging.info(f"Container status not ready {podName}:{containerName}")
                time.sleep(1)
                continue

            status = filteredContainerStatuses[0]
            if status.state.running:
                break
            else:
                time.sleep(2)
                continue


    def _copyDataToContainer(self, namespace, podName, containerName, task):
        corev1 = client.CoreV1Api(self._kube_client)

        for storagePath, containerPath in task.copyToContainerBeforeStart:
            logging.info(f"Copy dir in storage '{storagePath}' -> container '{namespace}:{podName}:{containerPath}'")
            exec_command = ['bash', '-c', f"cat | base64 -d | tar xvfz - -C {containerPath}"]
            resp = stream(
                corev1.connect_get_namespaced_pod_exec,
                podName,
                namespace,
                container=containerName,
                command=exec_command,
                stderr=True, stdin=True,
                stdout=True, tty=False,
                _preload_content=False
            )

            fileList = self._storage.list(storagePath)
            if len(fileList) == 0:
                continue

            with TemporaryFile() as tar_buffer:
                # write tar file
                with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                    for fileStat in fileList:
                        f, stat = self._storage.get(fileStat.path)
                        info = TarInfo(name=fileStat.path[len(storagePath):])
                        info.size = stat.size
                        tar.addfile(info ,fileobj=f)

                tar_buffer.flush()
                tar_buffer.seek(0)

                with TemporaryFile() as b64_encoded_tar:
                    with Base64IO(b64_encoded_tar) as b64_encoded_tar_buffer:
                        for line in tar_buffer.readlines():
                            b64_encoded_tar_buffer.write(line)

                    b64_encoded_tar.flush()
                    b64_encoded_tar.seek(0)

                    commands = []
                    commands.append(b64_encoded_tar.read())

                    while resp.is_open():
                        resp.update(timeout=1)
                        if resp.peek_stdout():
                            logger.debug("UPLOAD stdout: {}".format(resp.read_stdout()))
                        if resp.peek_stderr():
                            logger.debug("UPLOAD stderr: {}".format(resp.read_stderr()))
                        if commands:
                            c = commands.pop(0)
                            resp.write_stdin(c)
                        else:
                            break
            resp.close()

        # create done file
        exec_command = ['touch', '/tmp/done']
        resp = stream(
            corev1.connect_get_namespaced_pod_exec,
            podName,
            namespace,
            container=containerName,
            command=exec_command,
            stderr=True, stdin=False,
            stdout=True, tty=False,
            _preload_content=False
        )
        resp.close()

    def _copyDataFromContainer(self, namespace, podName, containerName, task):
        corev1 = client.CoreV1Api(self._kube_client)

        for containerPath, storagePath in task.copyFromContainerAfterFinish:
            logging.info(f"Copy dir to storage {storagePath} <- container '{namespace}:{podName}:{containerPath}'")
            exec_command = ['bash', '-c', f"tar cf - -C {containerPath} . | base64"]

            with TemporaryFile() as b64_encoded_buffer:
                resp = stream(
                    corev1.connect_get_namespaced_pod_exec,
                    podName,
                    namespace,
                    container=containerName,
                    command=exec_command,
                    stderr=True, stdin=True,
                    stdout=True, tty=False,
                    _preload_content=False)

                # write base64 encoded data into temporary file (b64_encoded_buffer).
                # reason we can not stream resp.read_stdout() directly into tarfile.open() to extract
                # is that resp object is not file object.
                #
                # Also, we can not decode base64 here, because each resp.read_stdout() might
                # return incomplete string to decode.
                while resp.is_open():
                    resp.update(timeout=1)
                    if resp.peek_stdout():
                        out = resp.read_stdout()
                        # print("STDOUT: %s" % len(out))
                        b64_encoded_buffer.write(out.encode())
                    if resp.peek_stderr():
                        logging.debug("DOWNLOAD stderr: %s" % resp.read_stderr())
                resp.close()
                b64_encoded_buffer.flush()
                b64_encoded_buffer.seek(0)

                # write base64 decoded data into another temporary file (tar_buffer).
                # Reason we can not pipe this data into Base64IO and stream into tarfile is,
                # that Base64IO returns file object that does not support seek(), which tarfile requires.
                with TemporaryFile() as tar_buffer:
                    with Base64IO(b64_encoded_buffer) as source:
                        for line in source:
                            tar_buffer.write(line)

                    tar_buffer.flush()
                    tar_buffer.seek(0)

                    with tarfile.open(fileobj=tar_buffer, mode='r:') as tar:
                        for info in tar.getmembers():
                            if not info.isfile():
                                continue

                            relPathInContainer = filename = info.name.lstrip("./") # info.name[len(containerPath):].lstrip("/").rstrip("/")
                            pathInStorage = f"""{storagePath.rstrip("/")}/{relPathInContainer}"""
                            f = tar.extractfile(info)
                            self._storage.put(f, pathInStorage)

        # create done file
        exec_command = ['touch', '/tmp/done']
        resp = stream(
            corev1.connect_get_namespaced_pod_exec,
            podName,
            namespace,
            container=containerName,
            command=exec_command,
            stderr=True, stdin=False,
            stdout=True, tty=False,
            _preload_content=False
        )
        resp.close()


    def _renderTemplate(self, templateText, task):
        context = self._getTemplateContext(task)
        context["task"] = task

        template = Template(templateText)
        rendered = template.render(context)

        return rendered

    def _renderTemplate(self, templateText, task):
        context = self._getTemplateContext(task)
        context["task"] = task

        template = Template(templateText)
        rendered = template.render(context)

        return rendered

    def _getTemplateContext(self, task):
        return {
            "k8s": {
                "namespace": self._namespace,
                "workspaceMount": Executor.SharedVolumeMount,
                "setupCommand": f"mkdir -p {Executor.ModelContainerPath} {Executor.EvalResultContainerPath} {Executor.ScoreResultContainerPath}",
                "envs": {
                    "CI": os.environ.get("CI", "false"),
                    "LUNA_WORKSPACE": Executor.SharedVolumeMount
                }
            }
        }

    def _getTemplate(self, templateFile):
        data = pkgutil.get_data(__name__, "template/{}".format(templateFile))
        return data.decode()

