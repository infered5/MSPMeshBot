from dataclasses import dataclass


@dataclass
class AdditionalInfoQuestion:
    json_name: str
    human_name: str
    question: str
    hide_if_mobile: bool


@dataclass
class StringQuestion(AdditionalInfoQuestion):
    min_length: int
    max_length: int


@dataclass
class BooleanQuestion(AdditionalInfoQuestion):
    pass


@dataclass
class NumberQuestion(AdditionalInfoQuestion):
    min_value: int
    max_value: int


@dataclass
class ChoiceQuestion(AdditionalInfoQuestion):
    choices: list[str]


additional_info_questions = [
    ChoiceQuestion(
        json_name="node_type",
        human_name="Node Type",
        question="What type of node is it?",
        choices=["Pocket", "Desk", "House", "Vehicle", "Infra", "Sensor"],
        hide_if_mobile=False,
    ),
    ChoiceQuestion(
        json_name="node_role",
        human_name="Node Role",
        question="What is the node's role?",
        choices=["Client", "Client_Mute", "Client_Hidden", "Client_Base", "Router", "Router_Late"],
        hide_if_mobile=False,
    ),
    StringQuestion(
        json_name="hardware_model",
        human_name="Hardware Model",
        question="What node hardware model is it?",
        min_length=1,
        max_length=64,
        hide_if_mobile=False,
    ),
    ChoiceQuestion(
        json_name="general_location",
        human_name="General Location",
        question="What is the general location of this node?",
        choices=[
            "Central Metro",
            "North Metro",
            "South Metro",
            "West Metro",
            "East Metro",
            "Greater MN",
            "Mankato",
            "Rochester",
            "Red River Valley",
            "Wisconsin",
        ],
        hide_if_mobile=False,
    ),
    ChoiceQuestion(
        json_name="location_set",
        human_name="Location Set",
        question="Does the node have GPS enabled?",
        choices=["GPS", "Static", "No"],
        hide_if_mobile=False,
    ),
    ChoiceQuestion(
        json_name="power_source",
        human_name="Power Source",
        question="How is the node powered?",
        choices=["Shore", "Solar", "Battery"],
        hide_if_mobile=False,
    ),
    BooleanQuestion(
        json_name="is_attended",
        human_name="Attended?",
        question="Is this node attended (someone is always there to monitor it)?",
        hide_if_mobile=False,
    ),
    # Antenna Information
    BooleanQuestion(
        json_name="antenna_above_roofline",
        human_name="Antenna Above Roofline?",
        question="Is the antenna above the roofline?",
        hide_if_mobile=True,
    ),
    NumberQuestion(
        json_name="antenna_dbi",
        human_name="Antenna dBi",
        question="What is the antenna gain in dBi? Numbers only.",
        min_value=0,
        max_value=100,
        hide_if_mobile=True,
    ),
    NumberQuestion(
        json_name="antenna_height",
        human_name="Antenna Height",
        question="How high is the base of the antenna above sea level in feet? This can be found using google earth or similar tools. Min 600, Max 2300",
        min_value=600,  # Lowest point in MN is Lake Superior at 600 feet above sea level
        max_value=2500,  # Highest point in MN is Eagle Mountain at 2301 feet above sea level
        hide_if_mobile=True,
    ),
    # Etc Information
    StringQuestion(
        json_name="notes",
        human_name="Notes",
        question="Any additional notes about this node?",
        min_length=1,
        max_length=256,
        hide_if_mobile=False,
    ),
]
