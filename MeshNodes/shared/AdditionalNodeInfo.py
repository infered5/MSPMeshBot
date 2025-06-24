from dataclasses import dataclass
import json
from pathlib import Path
from html import escape
import base64

@dataclass
class AdditionalInfoQuestion:
    json_name: str
    human_name: str
    question: str
    is_permanent_install: bool

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
    StringQuestion(
        json_name="hardware_model",
        human_name="Hardware Model",
        question="What node hardware model is it?",
        min_length=1,
        max_length=64,
        is_permanent_install=False
    ),
    StringQuestion(
        json_name="notes",
        human_name="Notes",
        question="Any additional notes about this node?",
        min_length=1,
        max_length=256,
        is_permanent_install=False
    ),
    ChoiceQuestion(
        json_name="node_role",
        human_name="Node Role",
        question="What is the node's role?",
        choices=["Client", "Client_Mute", "Router", "Router_Late"],
        is_permanent_install=False
    ),
    ChoiceQuestion(
        json_name="node_type",
        human_name="Node Type",
        question="What type of node is it?",
        choices=["Pocket", "Desk", "House", "Vehicle", "Infra", "Sensor"],
        is_permanent_install=False
    ),
    ChoiceQuestion(
        json_name="general_location",
        human_name="General Location",
        question="What is the general location of this node?",
        choices=["Central Metro", "North Metro", "South Metro", "West Metro", "East Metro", "Greater MN", "Mankato", "Rochester", "Red River Valley", "Wisconsin"],
        is_permanent_install=False
    ),
    ChoiceQuestion(
        json_name="location_set",
        human_name="Location Set",
        question="Does the node have GPS enabled?",
        choices=["GPS", "Static", "No"],
        is_permanent_install=False
    ),
    ChoiceQuestion(
        json_name="power_source",
        human_name="Power Source",
        question="How is the node powered?",
        choices=["Shore", "Solar", "Battery"],
        is_permanent_install=False
    ),
    BooleanQuestion(
        json_name="is_attended",
        human_name="Attended?",
        question="Is this node attended (someone is always there to monitor it)?",
        is_permanent_install=False
    ),
    BooleanQuestion(
        json_name="antenna_above_roofline",
        human_name="Antenna Above Roofline?",
        question="Is the antenna above the roofline?",
        is_permanent_install=True
    ),
    NumberQuestion(
        json_name="antenna_dbi",
        human_name="Antenna dBi",
        question="What is the antenna gain in dBi?",
        min_value=0,
        max_value=100,
        is_permanent_install=True
    ),
    NumberQuestion(
        json_name="antenna_height",
        human_name="Antenna Height",
        question="How high is the base of the antenna above sea level in feet? This can be found using google earth or similar tools.",
        min_value=600, # Lowest point in MN is Lake Superior at 600 feet above sea level
        max_value=2500, # Highest point in MN is Eagle Mountain at 2301 feet above sea level
        is_permanent_install=True
    )
]

def generate_html(questions, output_path):
    html_parts = [
        "<form id='infoForm'>"
    ]

    for q in questions:
        html_parts.append(f"<label for='{q.json_name}'><strong>{escape(q.human_name)}</strong><br>{escape(q.question)}</label><br>")
        if isinstance(q, StringQuestion):
            html_parts.append(
                f"<input type='text' id='{q.json_name}' name='{q.json_name}' minlength='{q.min_length}' maxlength='{q.max_length}' value=''><br><br>"
            )
        elif isinstance(q, BooleanQuestion):
            html_parts.append(
                f"<select id='{q.json_name}' name='{q.json_name}'>"
                f"<option value=''></option>"
                f"<option value='true'>Yes</option>"
                f"<option value='false'>No</option>"
                f"</select><br><br>"
            )
        elif isinstance(q, NumberQuestion):
            html_parts.append(
                f"<input type='number' id='{q.json_name}' name='{q.json_name}' min='{q.min_value}' max='{q.max_value}' value=''><br><br>"
            )
        elif isinstance(q, ChoiceQuestion):
            html_parts.append(f"<select id='{q.json_name}' name='{q.json_name}'>")
            html_parts.append("<option value=''></option>")
            for choice in q.choices:
                html_parts.append(f"<option value='{escape(choice)}'>{escape(choice)}</option>")
            html_parts.append("</select><br><br>")

    html_parts.append("<input type='submit' value='Submit'>")
    html_parts.append("</form>")

    html_parts.append("""
<pre id='output' style='margin-top: 2em; background: #eee; padding: 1em;'></pre>
<button id='copyBtn' style='display: none;'>Copy to Clipboard</button>
""")

    html_parts.append("""
<script>
document.getElementById('infoForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const form = e.target;
    const data = {};
    for (const element of form.elements) {
        if (!element.name || element.value === '') continue;
        if (element.tagName === 'SELECT' && (element.value === 'true' || element.value === 'false')) {
            data[element.name] = (element.value === 'true');
        } else if (element.type === 'number') {
            data[element.name] = Number(element.value);
        } else {
            data[element.name] = element.value;
        }
    }
    const json = JSON.stringify(data);
    const base64 = btoa(json);
    document.getElementById('output').textContent = base64;
    document.getElementById('copyBtn').style.display = 'inline';
});

document.getElementById('copyBtn').addEventListener('click', function() {
    const text = document.getElementById('output').textContent;
    navigator.clipboard.writeText(text);
});
</script>
""")

    Path(output_path).write_text("\n".join(html_parts), encoding='utf-8')


def parse_additional_info_base64(b64str: str) -> dict:
    """
    Decodes a base64 string produced by the HTML tool, parses it as JSON,
    and validates the values according to additional_info_questions.
    Only values present in the input are validated and included in the result.
    Returns the validated dictionary.
    Raises ValueError if any present value is invalid.
    """
    try:
        json_bytes = base64.b64decode(b64str)
        data = json.loads(json_bytes.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Invalid base64 or JSON: {e}")

    validated = {}
    for q in additional_info_questions:
        key = q.json_name
        if key not in data:
            continue
        value = data[key]
        if isinstance(q, StringQuestion):
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            if not (q.min_length <= len(value) <= q.max_length):
                raise ValueError(f"{key} length must be between {q.min_length} and {q.max_length}")
            validated[key] = value
        elif isinstance(q, BooleanQuestion):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            validated[key] = value
        elif isinstance(q, NumberQuestion):
            if not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number")
            if not (q.min_value <= value <= q.max_value):
                raise ValueError(f"{key} must be between {q.min_value} and {q.max_value}")
            validated[key] = value
        elif isinstance(q, ChoiceQuestion):
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string (choice)")
            if value not in q.choices:
                raise ValueError(f"{key} must be one of {q.choices}")
            validated[key] = value

    return validated


if __name__ == "__main__":
    generate_html(additional_info_questions, "additional_info_forum.html")