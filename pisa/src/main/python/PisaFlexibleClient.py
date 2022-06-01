from __future__ import print_function

import os
import json
from time import sleep

import grpc


from func_timeout import func_set_timeout
from grpc._channel import _InactiveRpcError

from pisa.src.main.python import server_pb2_grpc, server_pb2


class EnvInitFailedException(Exception):
    pass


class ProceedToLineFailedException(Exception):
    pass


class EmptyInitialStateException(Exception):
    pass


class StepToTopLevelStateException(Exception):
    pass


class IsaFlexEnv:
    def __init__(
        self,
        port,
        isa_path="/Applications/Isabelle2020.app/Isabelle",
        starter_string="theory Test imports Complex_Main begin",
        working_directory="/Users/qj213/Projects/afp-2021-02-11/thys/Functional-Automata",
    ):
        self.port = port
        self.isa_path = isa_path
        self.starter_string = starter_string
        self.working_directory = working_directory

        self.stub = None
        self.obs_string = None
        self.reset()

    def create_stub(self, port):
        self.channel = grpc.insecure_channel("localhost:{}".format(port))
        self.stub = server_pb2_grpc.ServerStub(self.channel)

    def observation(self):
        return self.obs_string

    def change_problem(self, new_theory_file_path):
        self.destroy_isabelle()
        working_directory = os.path.dirname(os.path.realpath(new_theory_file_path))
        print(
            self.stub.IsabelleWorkingDirectory(
                server_pb2.IsaPath(path=working_directory)
            )
        )
        print(
            self.stub.IsabelleContext(
                server_pb2.IsaContext(context=new_theory_file_path)
            )
        )

    @staticmethod
    def reward(done):
        return 1.0 if done else 0.0

    def reset(self):
        try:
            self.create_stub(port=self.port)
            print(self.stub.InitialiseIsabelle(server_pb2.IsaPath(path=self.isa_path)))
            print(
                self.stub.IsabelleWorkingDirectory(
                    server_pb2.IsaPath(path=self.working_directory)
                )
            )
            print(
                self.stub.IsabelleContext(
                    server_pb2.IsaContext(context=self.starter_string)
                )
            )
            self.initialize()
            return self.obs_string
        except _InactiveRpcError:
            raise EnvInitFailedException

    def destroy_isabelle(self):
        self.stub.IsabelleCommand(server_pb2.IsaCommand(command="exit"))
        self.channel.close()

    @func_set_timeout(10, allowOverride=True)
    def step_to_top_level_state(self, action, tls_name, new_name):
        try:
            obs_string = self.stub.IsabelleCommand(
                server_pb2.IsaCommand(
                    command=f"<apply to top level state> {tls_name} <apply to top level state> {action} <apply to top level state> {new_name}"
                )
            ).state
            if obs_string == "Step error":
                raise StepToTopLevelStateException
            done = self.get_proof_level(new_name) == 0
            return obs_string, self.reward(done), done, {}
        except _InactiveRpcError:
            raise StepToTopLevelStateException

    def initialize(self):
        initialise = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command=f"<initialise>")
        ).state

    def get_proof_level(self, tls_name):
        proof_level = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command=f"<get_proof_level> {tls_name}")
        ).state
        return int(proof_level)

    def clone_top_level_state(self, tls_name, old_name="default"):
        message = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command=f"<clone> {old_name} <clone> {tls_name}")
        ).state
        print(message)
        print(f"Cloned state called {tls_name}")

    @func_set_timeout(200, allowOverride=True)
    def proceed_to_line(self, line_string, before_after):
        assert before_after in ["before", "after"]
        try:
            obs_string = self.stub.IsabelleCommand(
                server_pb2.IsaCommand(command=f"<proceed {before_after}> {line_string}")
            ).state
            return obs_string
        except _InactiveRpcError:
            raise ProceedToLineFailedException

    def extract_theory_steps(self):
        all_steps_str = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command="PISA extract actions")
        ).state
        list_of_steps = all_steps_str.split("<\\ISA_STEP>")
        list_of_useful_steps = []
        for step in list_of_steps:
            if not step.startswith("(*") and len(step) > 0:
                list_of_useful_steps.append(step)
        return list_of_useful_steps

    def total_facts(self, tls_name):
        return self.stub.IsabelleCommand(
            server_pb2.IsaCommand(
                command=f"<total_facts> {tls_name}"
            )
        ).state

    def find_thm(self, tls_name, thm_name):
        return self.stub.IsabelleCommand(
            server_pb2.IsaCommand(
                command=f"<find_thm> {tls_name} <find_thm> {thm_name}"
            )
        ).state

    @func_set_timeout(20)
    def post(self, action):
        return self.stub.IsabelleCommand(server_pb2.IsaCommand(command=action)).state


def parsed_json_to_env_and_dict(
    path_to_json, afp_path, port, isa_path="/Applications/Isabelle2020.app/Isabelle"
):
    save_dict = json.load(open(path_to_json))
    project = save_dict["project"]
    wd = os.path.join(afp_path, "thys", project)
    segments = save_dict["segments"]
    # Find starter string
    starter_string = None
    for line in segments:
        if line.strip().startswith("theory"):
            starter_string = " ".join(line.strip().split("\n"))
            break
    assert starter_string
    return (
        IsaFlexEnv(
            port=port,
            isa_path=isa_path,
            starter_string=starter_string,
            working_directory=wd,
        ),
        save_dict,
    )


@func_set_timeout(300, allowOverride=True)
def initialise_env(port, isa_path, theory_file_path=None, working_directory=None, working_dir_mode="standard"):
    print(f"theory_file_path = {theory_file_path}")
    if working_directory is None:
        if working_dir_mode == "standard":
            theory_path_split = theory_file_path.split("/")
            if "thys" in theory_path_split:
                index = theory_path_split.index("thys")
                working_directory = "/".join(theory_path_split[: index + 2])
            elif "HOL" in theory_path_split:
                index = theory_path_split.index("HOL")
                if len(theory_path_split) < index + 2:
                    working_directory = "/".join(theory_path_split[: index + 1])
                else:
                    working_directory = "/".join(theory_path_split[: index + 2])
        elif working_dir_mode == "full":
            theory_path_split = theory_file_path.split("/")
            working_directory = "/".join(theory_path_split[: -1])

        else:
            assert ValueError(f"uknkown working_dir_mode = {working_dir_mode}")
            # if "thys" in theory_path_split:
            #     index = theory_path_split.index("thys")
            #     working_directory = "/".join(theory_path_split[: index + 2])
            # elif "HOL" in theory_path_split:
            #     index = theory_path_split.index("HOL")
            #     if len(theory_path_split) < index + 2:
            #         working_directory = "/".join(theory_path_split[: index + 1])
            #     else:
            #         working_directory = "/".join(theory_path_split[: index + 2])

        print(f"Automatically detected working directory: {working_directory}")
    return IsaFlexEnv(
        port=port,
        isa_path=isa_path,
        starter_string=theory_file_path,
        working_directory=working_directory,
    )


def initialise_problem(env, problem_name):
    env.proceed_to_line(problem_name, "after")
    return env
