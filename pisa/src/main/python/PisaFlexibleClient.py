from __future__ import print_function

import os
import json
import grpc
import sys

sys.path.append('/home/szymon/PycharmProjects/interactive_isabelle/pisa/src/main/python')



from copy import copy
from func_timeout import func_set_timeout

from pisa.src.main.python import server_pb2, server_pb2_grpc

# import server_pb2
# import server_pb2_grpc



MAX_MESSAGE_LENGTH = 10485760


# def create_stub(port=9000):
#     channel = grpc.insecure_channel('localhost:{}'.format(port),
#                                     options=[('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
#                                              ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)])
#     return server_pb2_grpc.ServerStub(channel)



class IsaFlexEnv:
    def __init__(self, port=9000, isa_path="/Applications/Isabelle2020.app/Isabelle",
                 starter_string="theory Test imports Complex_Main begin",
                 working_directory="/Users/qj213/Projects/afp-2021-02-11/thys/Functional-Automata"):
        self.port = port
        self.isa_path = isa_path
        self.starter_string = starter_string
        self.working_directory = working_directory

        self.stub = None
        self.obs_string = None
        self.reset()

    def create_stub(self, port):
        MAX_MESSAGE_LENGTH = 1048576000
        self.channel = grpc.insecure_channel('localhost:{}'.format(port),
                                             options=[('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                                                      ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)])
        return server_pb2_grpc.ServerStub(self.channel)

    def observation(self):
        return self.obs_string

    def initialise_env(self,port, isa_path, theory_file_path=None, working_directory=None):
        return IsaFlexEnv(port=port, isa_path=isa_path, starter_string=theory_file_path,
                          working_directory=working_directory)

    def is_finished(self, name_of_tls):
        returned_string = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=f"<is finished> {name_of_tls}")).state.strip()
        if returned_string.startswith("t"):
            return True
        else:
            return False

    @staticmethod
    def reward(done):
        return 1. if done else 0.

    def reset(self):
        print(self.port)
        self.stub = self.create_stub(port=self.port)
        print("Hooray")
        try:
            print(self.stub.InitialiseIsabelle(server_pb2.IsaPath(path=self.isa_path)))
            print(self.stub.IsabelleWorkingDirectory(server_pb2.IsaPath(path=self.working_directory)))
            print(self.stub.IsabelleContext(server_pb2.IsaContext(context=self.starter_string)))
        except Exception as e:
            print("Failure at initialising Isabelle process. "
                  "Make sure the path your provide is where the Isabelle executable is.")
            print(e)
        return self.obs_string

    def get_proof_level(self, tls_name):
        proof_level = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command=f"<get_proof_level> {tls_name}")
        ).state
        return int(proof_level)

    def dependent_theorems(self, theorem_name):
        # print(theorem_name)
        theorems = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=f"<get_thm_deps> {theorem_name}")).state
        return theorems.split("<SEP>")

    @func_set_timeout(20)
    def step_to_top_level_state(self, action, tls_name, new_name):
        # last_obs_string = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=f"<get state> {tls_name}")).state
        try:
            obs_string = self.stub.IsabelleCommand(
                server_pb2.IsaCommand(command=f"<apply to top level state> {tls_name} <apply to top level state> {action} <apply to top level state> {new_name}")).state
        except Exception as e:
            print("***Something went wrong***")
            print(e)

        done = self.is_finished(new_name)
        # done = True if ("subgoal" in last_obs_string and "subgoal" not in obs_string) else False
        return obs_string, self.reward(done), done, {}

    @func_set_timeout(60)
    def post(self, action):
        return self.stub.IsabelleCommand(server_pb2.IsaCommand(command=action)).state
        # last_obs_string = self.obs_string
        # try:
        #     self.obs_string = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=action)).state
        # except Exception as e:
        #     print("***Something went wrong***")
        #     print(e)

        # # done = self.is_finished(self.obs_string)
        # done = self.is_finished("default")

        # return self.obs_string, self.reward(done), done, {}

    # def human_play(self):
    #     done = False
    #     while not done:
    #         print(self.obs_string)
    #         human_proof_line = input("Your tactic is my command: ")
    #         if human_proof_line == "exit":
    #             break
    #         else:
    #             obs, _, done, _ = self.step(human_proof_line)
    #             print(obs)
    #             print("=" * 50)

    # def clone_top_level_state(self, tls_name):
    #     try:
    #         message = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=f"<clone> {tls_name}")).state
    #         print(message)
    #         print(f"Cloned state called {tls_name}")
    #     except Exception as e:
    #         print("**Clone unsuccessful**")
    #         print(e)

    # def proceed_to_line(self, line_stirng, before_after):
    #     assert before_after in ["before", "after"]
    #     try:
    #         message = self.stub.IsabelleCommand(server_pb2.IsaCommand(command=f"<proceed {before_after}> {line_stirng}")).state
    #         print(message)
    #     except Exception as e:
    #         print("Failure to proceed before line")
    #         print(e)
    def extract_theory_steps(self):
        all_steps_str = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command="<extract_steps>")
        ).state
        list_of_steps = all_steps_str.split("<\\ISA_STEP>")
        list_of_useful_steps = []
        for step in list_of_steps:
            if not step.startswith("(*") and len(step) > 0:
                list_of_useful_steps.append(step)
        return list_of_useful_steps

    def clone_top_level_state(self, tls_name, old_name="default"):
        message = self.stub.IsabelleCommand(
            server_pb2.IsaCommand(command=f"<clone> {old_name} <clone> {tls_name}")
        ).state
        print(message)
        print(f"Cloned state called {tls_name}")

############################ THIS IS NEW, ADAPTED FROM ALBERT ##################################
    def local_facts(self, tls_name="default"):
        try:
            return self.post(f"<local facts and defs> {tls_name}")
        except:
            return "failed"
        # return self.stub.IsabelleCommand(
        #     server_pb2.IsaCommand(
        #         command=f"<local_facts> {tls_name}"
        #     )
        # ).state

    def global_facts(self, tls_name="default"):
        return self.post(f"<global facts and defs> {tls_name}")
        # return self.stub.IsabelleCommand(
        #     server_pb2.IsaCommand(
        #         command=f"<global_facts> {tls_name}"
        #     )
        # ).state

    def find_thm(self, tls_name, thm_name):
        return self.stub.IsabelleCommand(
            server_pb2.IsaCommand(
                command=f"<find_thm> {tls_name} <find_thm> {thm_name}"
            )
        ).state

    def destroy_isabelle(self):
        self.stub.IsabelleCommand(server_pb2.IsaCommand(command="exit"))
        self.channel.close()

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

def parsed_json_to_env_and_dict(path_to_json, afp_path, port=9000, isa_path="/Applications/Isabelle2020.app/Isabelle"):
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
    # print(port, isa_path, starter_string, wd, segments)
    return IsaFlexEnv(port=port, isa_path=isa_path,
                     starter_string=starter_string,
                     working_directory=wd), save_dict


# def initialise_env(port, isa_path, theory_file_path=None, working_directory=None, working_dir_mode="standard"):
#     return IsaFlexEnv(port=port, isa_path=isa_path, starter_string=theory_file_path, working_directory=working_directory)

@func_set_timeout(300, allowOverride=True)
def initialise_env(port, isa_path, theory_file_path=None, working_directory=None, working_dir_mode="standard"):
    print(isa_path)
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



if __name__ == '__main__':
    env = initialise_env(8000,
        working_directory="/Applications/Isabelle2021.app/src/HOL/Examples",
        isa_path="/Applications/Isabelle2021.app",
        theory_file_path="/Applications/Isabelle2021.app/src/HOL/Examples/Adhoc_Overloading_Examples.thy"
    )
    print(env.post("<get_ancestors>"))
