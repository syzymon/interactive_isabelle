from PisaFlexibleClient import IsaFlexEnv

if __name__ == "__main__":
    isa_path = "/home/szymon/Isabelle2021"
    working_directory = "/home/szymon/ATP_new/afp-2021-10-22/thys/Simpl"
    file_path = working_directory + "/Hoare.thy"
    env = IsaFlexEnv(
        port=8000, isa_path=isa_path, starter_string=file_path,
        working_directory=working_directory,
    )

    theorem_string = '    by (auto simp add: wf_iff_no_infinite_down_chain)'

    env.post(f"<proceed after> {theorem_string}")
    env.post("<initialise>")
    for i in env.global_facts().split("<SEP>"):
    # for i in env.post("<global facts and defs> default").split("<SEP>"):
        print(i)
        break
