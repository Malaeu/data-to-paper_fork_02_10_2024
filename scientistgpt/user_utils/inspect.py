import glob
import os
import shutil

from pathlib import Path
from typing import List

from scientistgpt import Conversation, ScientistGPT
from scientistgpt.conversation.conversation import OPENAI_SERVER_CALLER
from scientistgpt.conversation.actions_and_conversations import save_actions_to_file
from scientistgpt.data_file_description import DataFileDescription
from scientistgpt.gpt_interactors.citation_adding.call_crossref import CROSSREF_SERVER_CALLER
from scientistgpt.run_gpt_code.dynamic_code import module_dir


ACTIONS_FILENAME = 'conversation_actions.pkl'
OPENAI_RESPONSES_FILENAME = 'openai_responses.txt'
CROSSREF_RESPONSES_FILENAME = 'crossref_responses.txt'


def run_scientist_gpt(data_file_descriptions: List[DataFileDescription],
                      research_goal: str,
                      data_directory: str, output_directory: str,
                      mock_servers: bool = False):
    """
    Run ScientistGPT, and save all files generated by ScientistGPT to a specified output folder.
    """
    data_directory = Path(data_directory).absolute()
    output_directory = Path(output_directory).absolute()

    # Create empty output folder (delete if exists):
    if os.path.exists(output_directory):
        # delete all the files except the mock_openai file:
        for file in glob.glob(str(output_directory / '*')):
            if file != str(output_directory / OPENAI_RESPONSES_FILENAME):
                os.remove(file)
    else:
        os.makedirs(output_directory)

    runner = ScientistGPT(data_file_descriptions=data_file_descriptions, research_goal=research_goal,
                          data_directory=data_directory, output_directory=output_directory)

    @CROSSREF_SERVER_CALLER.record_or_replay(output_directory / CROSSREF_RESPONSES_FILENAME, should_mock=mock_servers)
    @OPENAI_SERVER_CALLER.record_or_replay(output_directory / OPENAI_RESPONSES_FILENAME, should_mock=mock_servers)
    def run():
        runner.run_all()

    absolute_home_path = Path().absolute()

    # we run in the data folder, so that chatgpt finds our files:
    try:
        os.chdir(data_directory)
        run()
    finally:
        os.chdir(absolute_home_path)
        save_all_files_to_output_folder(output_directory, data_directory)


def view_saved_conversation(filename: str):
    Conversation.from_file(filename).print_all_messages()


def save_all_files_to_output_folder(output_directory, absolute_data_path):
    """
    Save all files generated by ScientistGPT to a specified output folder.
    """
    from scientistgpt import ScientistGPT
    # Save conversation to text file:
    save_actions_to_file(output_directory / ACTIONS_FILENAME)

    # Move all gpt analysis result files to output folder:
    for file in glob.glob(str(absolute_data_path / (ScientistGPT.gpt_script_filename + '*.txt'))):
        shutil.move(file, output_directory)

    # Move all gpt analysis scripts to output folder:
    for file in glob.glob(str(Path(module_dir) / (ScientistGPT.gpt_script_filename + '*.py'))):
        shutil.move(file, output_directory)

    # Move all gpt generated plots to output folder:
    for file in glob.glob(str(absolute_data_path / '*.png')):
        shutil.move(file, output_directory)

    # TODO: this one is risky cs it might move our own data files (if they have .txt extension)
    # Move gpt generated txt files to output folder:
    for file in glob.glob(str(absolute_data_path / '*.txt')):
        shutil.move(file, output_directory)

    # Move gpt generated pdf files to output folder:
    for file in glob.glob(str(absolute_data_path / '*.pdf')):
        shutil.move(file, output_directory)
